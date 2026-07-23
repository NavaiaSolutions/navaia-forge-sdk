#!/usr/bin/env python3
"""Decide whether a scraped listing IS one of the three active verticals.

    python scripts/lead_qualify.py --self-test          # offline, no spend
    python scripts/lead_qualify.py --self-test --llm    # live, costs a few cents

## Why this is a judgement step and not a keyword match

`distill_scraped_leads.guess_sector` decides the vertical with
`any(keyword in f"{name} {category}".lower())`. The workforce preamble spends a paragraph
insisting on distinctions that substring matching structurally cannot make:

  * a carpentry or joinery shop is NOT "Contracting & Facilities" — that means real
    contracting / facilities-management firms with proposals or operations teams
  * a freelance tutor or a driving school is NOT a "Training Institute" — that means
    licensed training centres with course delivery and enrolment operations
  * a lone broker with no registered office is NOT "Real Estate" — that means established
    agencies and property-management companies

A workshop with مقاولات in its name matched "Contracting" every single time. The cost of
that error is not a wasted row: the lead receives real Arabic outreach about a pain it does
not have, under the operator's name.

## What it is NOT allowed to do

* It cannot invent a vertical. Anything outside the three active names is discarded here in
  Python, not trusted from the model.
* It cannot promote a lead the keyword pass rejected as RETIRED — retired verticals are an
  operator decision, not a judgement call.
* It cannot pass a lead on thin evidence. "Unsure" means DROP, because a wrong-fit contact
  wastes send budget and burns the channel, while a dropped lead costs nothing but itself.

## Failure is not a verdict

If the call fails, times out, or returns something unparseable, the KEYWORD guess stands and
`source` says `error`. A qualification step that silently dropped every lead when the key
expired would empty the pipeline and look like "no businesses matched" — the same class of
silent failure as the dead OpenRouter key.
"""
from __future__ import annotations

import argparse
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import review_pains                       # shared model plumbing; rebinds stdout on import
import nav_env

ACTIVE_VERTICALS = ("Real Estate", "Contracting & Facilities", "Training Institutes")

# Cheaper than the pain model on purpose: this is a short classification over a few fields,
# not dialect comprehension over a page of reviews. Override per deployment.
MODEL = nav_env.env("QUALIFY_MODEL", "qwen/qwen3-235b-a22b") or "qwen/qwen3-235b-a22b"


def build_prompt(lead: dict, guess: str) -> str:
    fields = [
        f"name: {lead.get('name') or '(none)'}",
        f"maps category: {lead.get('category') or '(none)'}",
        f"address: {lead.get('address') or '(none)'}",
        f"website: {lead.get('website') or '(none)'}",
        f"review count: {lead.get('review_count') if lead.get('review_count') not in (None, '') else '(unknown)'}",
        f"rating: {lead.get('rating') if lead.get('rating') not in (None, '') else '(unknown)'}",
    ]
    return (
        "You are qualifying a scraped Google Maps listing for a Saudi B2B sales pipeline "
        "that sells operational automation to established SMBs in Riyadh.\n\n"
        "Decide which ONE of these three verticals the business genuinely IS, or none:\n"
        "  - Real Estate: established agencies and property-management companies\n"
        "  - Contracting & Facilities: real contracting or facilities-management firms, "
        "with proposals or operations teams\n"
        "  - Training Institutes: licensed training centres with course delivery and "
        "enrolment operations\n\n"
        "It must BE the vertical, not merely keyword-match it. Specifically:\n"
        "  - a carpentry, joinery or metalwork workshop is NOT Contracting & Facilities\n"
        "  - a single freelance tutor or a driving school is NOT a Training Institute\n"
        "  - a lone broker with no registered office is NOT Real Estate\n"
        "  - sole-proprietor and informal trades (handyman, small workshop, corner retail) "
        "are excluded whatever they are called\n"
        "  - clinics, medical, financial and debt-collection businesses are OUT OF SCOPE; "
        "return \"\" for them\n\n"
        "Judge ONLY from the fields below. Do not use outside knowledge of the company and "
        "do not guess at facts that are not shown. If the evidence is thin or ambiguous, "
        "return \"\" — dropping a borderline lead is correct and cheap; contacting a "
        "wrong-fit business is not.\n\n"
        f"A keyword pass guessed: {guess or '(nothing)'}. Treat that as a hint you may "
        "freely overrule; it matches substrings and is often wrong.\n\n"
        + "\n".join(fields) + "\n\n"
        'Return ONLY JSON: {"vertical":"Real Estate"|"Contracting & Facilities"|'
        '"Training Institutes"|"", "reason":"<8 words or fewer>"}'
    )


def qualify(lead: dict, guess: str, key: str | None, *, spend: bool = True) -> dict:
    """Return {"sector", "reason", "source"} where source is llm|keyword|error|skipped.

    `sector` is "" when the lead is not one of the three active verticals — that is a
    verdict, not a failure, and the caller should drop the lead.
    """
    # A RETIRED verdict from the keyword pass is an operator decision about which markets we
    # sell to. The model is not consulted and cannot overturn it.
    if (guess or "").startswith("RETIRED:"):
        return {"sector": "", "reason": f"{guess} — retired vertical", "source": "keyword"}

    if not spend or not key:
        return {"sector": guess if guess in ACTIVE_VERTICALS else "",
                "reason": "keyword guess (qualification not run)", "source": "skipped"}

    parsed = review_pains.call_model(build_prompt(lead, guess), key,
                                     model=MODEL, label="qualify")
    if parsed is None:
        # Fail SOFT, and say so. Emptying the pipeline on a dead key would look exactly
        # like "no businesses matched".
        return {"sector": guess if guess in ACTIVE_VERTICALS else "",
                "reason": "model call failed — keyword guess stands", "source": "error"}

    vertical = str(parsed.get("vertical") or "").strip()
    reason = str(parsed.get("reason") or "").strip()[:80]

    # Never trust the label. Anything outside the three active names is a drop, which also
    # covers a model that invents a vertical or echoes a retired one.
    if vertical not in ACTIVE_VERTICALS:
        return {"sector": "", "reason": reason or "not an active vertical", "source": "llm"}
    return {"sector": vertical, "reason": reason, "source": "llm"}


# ── self-test ────────────────────────────────────────────────────────────────────────

CASES = [
    # (lead, keyword guess, expected_sector_or_None_for_any, why this case exists)
    ({"name": "مؤسسة النجار للأثاث والديكور", "category": "Carpenter"},
     "Contracting & Facilities", "",
     "carpentry workshop — the exact false positive keyword matching produces"),
    ({"name": "شركة الرياض للمقاولات العامة", "category": "General contractor",
      "website": "riyadh-contracting.example", "review_count": 40},
     "Contracting & Facilities", "Contracting & Facilities",
     "a real contracting firm must still pass"),
    ({"name": "مدرسة تعليم قيادة السيارات", "category": "Driving school"},
     "Training Institutes", "",
     "driving school is not a training institute"),
    ({"name": "عيادة الأسنان التخصصية", "category": "Dental clinic"},
     "RETIRED:Private Clinics", "",
     "retired vertical is refused WITHOUT consulting the model"),
    ({"name": "مكتب الوساطة العقارية", "category": "Real estate agency",
      "website": "aqar-example.test", "review_count": 25},
     "Real Estate", None,
     "an established agency — either verdict is defensible, must not crash"),
]


def _self_test(key: str | None) -> int:
    """Offline asserts the FALLBACK contract; --llm asserts the judgement itself.

    Offline, the keyword guess stands by design — so the carpentry and driving-school cases
    return the wrong vertical, and that is the correct offline behaviour, not a failure. It
    is also a neat demonstration of why this module exists: those are exactly the verdicts
    substring matching produces. Only the live run can assert the judgement.
    """
    live = bool(key)
    print(f"lead_qualify self-test ({'LIVE' if live else 'offline — asserts fallback only'})\n")
    failed = 0
    for lead, guess, expect, why in CASES:
        got = qualify(lead, guess, key, spend=live)
        if not live:
            # Offline contract: retired is refused outright, everything else falls back to
            # the keyword guess untouched.
            want = "" if guess.startswith("RETIRED:") else (
                guess if guess in ACTIVE_VERTICALS else "")
            ok = got["sector"] == want
        else:
            ok = expect is None or got["sector"] == expect
        if not ok:
            failed += 1
        print(f"  {'PASS' if ok else 'FAIL'}  {lead['name'][:34]:34} "
              f"guess={guess[:24]:24} -> {got['sector'] or '(dropped)':24} "
              f"[{got['source']}] {got['reason'][:40]}")
        print(f"        {why}")
    print(f"\n{len(CASES) - failed}/{len(CASES)} passed")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--llm", action="store_true", help="run the cases LIVE (costs a little)")
    args = ap.parse_args()
    if not args.self_test:
        ap.print_help()
        return 0
    return _self_test(nav_env.openrouter_key() if args.llm else None)


if __name__ == "__main__":
    sys.exit(main())

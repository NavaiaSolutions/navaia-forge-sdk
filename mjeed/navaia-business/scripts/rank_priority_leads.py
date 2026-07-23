#!/usr/bin/env python3
"""Rank Not Contacted CRM leads for the "50+ employees" priority rule — using only
data already on disk. No API credits, no crawling, no external calls.

The LOCAL, deterministic stand-in for Nora's scoring step (script-authority doctrine,
workforce/POSTMORTEM_2026-07-14.md), so the ranking is reproducible and auditable
instead of re-derived by an LLM on every run.

WHAT THIS DOES NOT DO — read this before trusting a number here:
There is no headcount data in the pipeline. Twenty's `employees` field is empty on
every one of Mjeed's companies and no LinkedIn URLs are stored. The authoritative
Saudi sources (GOSI/Qiwa via Wathq) are consent-gated to the establishment itself and
are not lawful prospecting sources under PDPL. So this script does NOT report employee
counts. It reports a SIZE PROXY built from free signals, and the proxy is a hypothesis
to be confirmed on the two or three leads you actually pick — not a measurement.

Size proxy signals (all free, all from leads_scraped_compact.json + the CRM):
  branches      multiple pool listings sharing a name/domain  -> strongest free signal
  legal form    مجموعة/قابضة/شركة  outrank  مؤسسة/مكتب        -> Saudi naming convention
  own domain    a real company domain, not aqar.fm/glitch.me  -> operational maturity
  review volume Google review count as an operations-scale hint (NOT headcount)

Confirming a shortlisted lead's real size is a separate, deliberate step:
`scripts/enrich_company_size.py` (self-published website claims). Run it only on the
leads you choose, so the spend stays where you pointed it.

Usage:
    python scripts/rank_priority_leads.py                  # full ranking
    python scripts/rank_priority_leads.py --top 15         # shortlist
    python scripts/rank_priority_leads.py --top 15 --json shortlist.json
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pipeline_prep as prep

POOL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                    "leads_scraped_compact.json")
ACTIVE_VERTICALS = ["Real Estate", "Contracting & Facilities", "Training Institutes"]

# Saudi legal-form words, ordered by the scale they usually imply. A "مجموعة" or a
# "شركة ... القابضة" is a multi-entity operation; a "مكتب" is typically an owner plus a
# handful of staff. This is convention, not law — hence a proxy tier, not a headcount.
_FORM_LARGE = re.compile(r"(مجموعة|القابضة|قابضة|شركة\s+.*\s+(الدولية|العالمية)|Group|Holding)", re.I)
_FORM_MID = re.compile(r"(شركة|Company|Co\.|L\.?L\.?C)", re.I)
_FORM_SMALL = re.compile(r"(مكتب|مؤسسة|Office|Est\.?)", re.I)

# Hosts that mean the business has NO real web presence of its own — a portal profile
# or a free page. Strong negative signal for a 50+ operation. The list now lives in
# pipeline_prep so the enrichment and send paths obey the same rule this one scores on;
# they didn't, and that sent a lead's outreach to a portal on 2026-07-21.
_NOT_OWN_DOMAIN = prep._NOT_OWN_DOMAIN


def _pool() -> list[dict]:
    with io.open(POOL, encoding="utf-8") as f:
        return json.load(f)


def _pool_index() -> tuple[dict, dict, dict]:
    """Phone-keyed pool index, plus name/domain -> branch counts for the branch signal."""
    by_phone, name_counts, domain_counts = {}, {}, {}
    for lead in _pool():
        phone = prep._phone9(lead.get("phone") or "")
        if phone:
            by_phone[phone] = lead
        # Branch detection: strip a trailing branch parenthetical, then count the stem.
        stem = re.sub(r"\s*[\(（][^)）]*[\)）]\s*$", "", (lead.get("name") or "")).strip()
        if stem:
            name_counts[stem] = name_counts.get(stem, 0) + 1
        # Portal hosts are excluded deliberately: a hundred agencies share aqar.fm,
        # and counting that as "100 branches" would score every one of them as huge.
        host = prep._domain_of(lead.get("website") or "")
        if host:
            domain_counts[host] = domain_counts.get(host, 0) + 1
    return by_phone, name_counts, domain_counts


def size_proxy(lead: dict, pool_row: dict, branches: int) -> tuple[int, list[str]]:
    """0-100 likelihood that this is a 50+ employee operation. A HYPOTHESIS, not a count."""
    score, signals = 0, []
    name = lead.get("company") or ""

    if branches >= 3:
        score += 40
        signals.append(f"branches:{branches}")
    elif branches == 2:
        score += 25
        signals.append("branches:2")

    if _FORM_LARGE.search(name):
        score += 30
        signals.append("form:group/holding")
    elif _FORM_MID.search(name):
        score += 15
        signals.append("form:company")
    elif _FORM_SMALL.search(name):
        score -= 10
        signals.append("form:office/est(small)")

    site = lead.get("website") or ""
    if site and prep.is_own_domain(site):
        score += 20
        signals.append("own_domain")
    elif site:
        score -= 10
        signals.append("portal_page_only")

    try:
        reviews = int(float(pool_row.get("review_count") or 0))
    except (TypeError, ValueError):
        reviews = 0
    if reviews >= 200:
        score += 15
        signals.append(f"reviews:{reviews}")
    elif reviews >= 75:
        score += 8
        signals.append(f"reviews:{reviews}")

    return max(0, min(score, 100)), signals


def reachability(lead: dict) -> tuple[int, list[str]]:
    """Can we actually run outreach at this lead, and will the message be personalised?"""
    score, signals = 0, []
    if lead.get("email"):
        score += 25
        signals.append("email")
    if lead.get("phone"):
        score += 20
        signals.append("phone/wa")
    if lead.get("pain_line"):
        score += 20
        signals.append("own_review_pain")
    if lead.get("contact_name"):
        score += 10
        signals.append("named_contact")
    return score, signals


def rank(verticals: list[str] | None = None) -> list[dict]:
    by_phone, name_counts, domain_counts = _pool_index()
    out = []
    for lead in prep.not_contacted_leads(verticals or ACTIVE_VERTICALS):
        phone = prep._phone9(lead.get("phone") or "")
        pool_row = by_phone.get(phone, {})
        stem = re.sub(r"\s*[\(（][^)）]*[\)）]\s*$", "",
                      pool_row.get("name") or lead.get("company") or "").strip()
        host = urlparse(lead.get("website") or "").netloc.lower().replace("www.", "")
        branches = max(name_counts.get(stem, 0), domain_counts.get(host, 0) if host else 0)

        size, size_sig = size_proxy(lead, pool_row, branches)
        reach, reach_sig = reachability(lead)
        out.append({**lead,
                    "size_proxy": size, "size_signals": size_sig,
                    "reach": reach, "reach_signals": reach_sig,
                    # Size leads the sort (it is the operator's priority rule); reach breaks
                    # ties, because an unreachable giant produces no outreach at all.
                    "priority": round(size * 0.7 + reach * 0.3),
                    "reviews": pool_row.get("review_count") or "",
                    "category": pool_row.get("category") or ""})
    out.sort(key=lambda r: (r["priority"], r["size_proxy"], r["reach"]), reverse=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verticals", default=",".join(ACTIVE_VERTICALS))
    ap.add_argument("--top", type=int, default=0)
    ap.add_argument("--json", dest="json_out")
    args = ap.parse_args()

    verticals = [v.strip() for v in args.verticals.split(",") if v.strip()]
    ranked = rank(verticals)
    shown = ranked[: args.top] if args.top else ranked

    print(f"Ranked {len(ranked)} Not Contacted leads in {verticals}")
    print("SIZE IS A PROXY, NOT A HEADCOUNT — confirm the ones you pick.\n")
    print(f"{'#':>3}  {'pri':>3} {'size':>4} {'rch':>3}  {'sector':22} {'company':38} signals")
    for i, r in enumerate(shown, 1):
        print(f"{i:3}. {r['priority']:3} {r['size_proxy']:4} {r['reach']:3}  "
              f"{r['sector'][:22]:22} {r['company'][:38]:38} "
              f"{','.join(r['size_signals'] + r['reach_signals'])}")

    if args.json_out:
        with io.open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(shown, f, ensure_ascii=False, indent=1)
        print(f"\nWrote {len(shown)} leads -> {args.json_out}")


if __name__ == "__main__":
    main()

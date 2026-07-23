#!/usr/bin/env python3
"""Render the FINISHED Snov email for a lead, before anyone receives it.

    python scripts/snov_preview.py --vertical "Real Estate"
    python scripts/snov_preview.py --vertical "Real Estate" --llm      # real generated Arabic
    python scripts/snov_preview.py --leads-file leads.json --limit 3

## Why this exists

Moving the email body to Snov bought the PDF attachment and cost the review step. The local
render in `outreach.py` still shows the OLD repo template, so for the email channel it now
shows something that will never be sent — worse than no preview, because it looks like one.

Only `{{pain_block}}` is generated here. Everything around it is invisible to us: Snov exposes
no template API (all endpoints 404, probed 2026-07-21), so the surrounding text cannot be read
back. This stitches the mirrored body from `workforce/snov_campaign_bodies.md` around the
generated block so a human can read the whole message before a stranger does.

**The mirror can drift.** Snov is authoritative; this file is hand-kept. A preview from a stale
mirror still beats no preview, but never treat it as proof of what Snov holds — check the
dashboard when something looks wrong.

Sends nothing. Touches no CRM. Safe to run at any time.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import lina_compose
import nav_env

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BODIES = os.path.join(ROOT, "workforce", "snov_campaign_bodies.md")

# CRM sector -> lina_compose library key.
VERTICAL_KEY = {
    "Real Estate": "realestate",
    "Contracting & Facilities": "contracting",
    "Training Institutes": "training",
}


def load_bodies() -> dict[str, dict[str, str]]:
    """{vertical: {"subject": ..., "body": ..., "campaign": ...}} from the mirror file."""
    text = io.open(BODIES, encoding="utf-8").read()
    out: dict[str, dict[str, str]] = {}
    for m in re.finditer(
            r"###\s*(.+?)\s*\(campaign\s*(\d+)\)\s*\n+\*\*subject:\*\*\s*(.+?)\n+```\n(.*?)```",
            text, re.S):
        vertical, campaign, subject, body = (m.group(1).strip(), m.group(2),
                                             m.group(3).strip(), m.group(4).strip())
        out[vertical] = {"subject": subject, "body": body, "campaign": campaign}
    return out


def render(body: str, subject: str, lead: dict, block: str) -> tuple[str, str]:
    """Substitute exactly the variables Snov will substitute — no more."""
    values = {
        "first_name": (lead.get("first_name")
                       or (lead.get("contact_name") or "").split(" ")[0]),
        "company_name": lead.get("company") or "",
        "pain_block": block,
        # Identical call to the one snov_push makes, so the preview cannot disagree with
        # what is actually pushed.
        "greeting": lina_compose.greeting(lead.get("contact_name") or "",
                                          lead.get("company") or ""),
    }
    # first_name is optional once {{greeting}} exists: the body no longer uses it, and a
    # lead with no personal name is greeted at company level rather than skipped.
    missing = [k for k, v in values.items()
               if not str(v).strip() and ("{{%s}}" % k) in body]
    for k, v in values.items():
        body = body.replace("{{%s}}" % k, str(v))
        subject = subject.replace("{{%s}}" % k, str(v))
    if missing:
        # Not cosmetic: these campaigns set skip_recipients_without_variables_data=true, so
        # Snov DROPS such a recipient rather than mailing a gap. A lead that looks fine here
        # would simply never be sent, and nothing would report it as a failure.
        print(f"  !! MISSING {missing} — Snov will SKIP this recipient, not mail them")
    return subject, body


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vertical", default="Real Estate")
    ap.add_argument("--leads-file", help="JSON list of leads; omit to preview one demo lead")
    ap.add_argument("--limit", type=int, default=1)
    ap.add_argument("--llm", action="store_true",
                    help="generate the real per-lead block (COSTS a little money). "
                         "Without it the library block is shown, which is the floor.")
    args = ap.parse_args()

    bodies = load_bodies()
    if args.vertical not in bodies:
        raise SystemExit(f"No mirrored body for {args.vertical!r}. Have: {list(bodies)}")
    tpl = bodies[args.vertical]
    vkey = VERTICAL_KEY.get(args.vertical)
    if not vkey:
        raise SystemExit(f"{args.vertical!r} is not an active vertical.")

    if args.leads_file:
        with io.open(args.leads_file, encoding="utf-8") as f:
            data = json.load(f)
        leads = (data.get("leads", data) if isinstance(data, dict) else data)[:args.limit]
    else:
        leads = [{"company": "مكتب الريادة العقارية", "contact_name": "سارة القحطاني",
                  "pain_summary": "The company is slow to respond to enquiries and does "
                                  "not follow up with interested buyers.",
                  "pains": [{"pain": "slow_reply", "count": 3, "reviewed": 8, "share": 0.375},
                            {"pain": "no_followup", "count": 2, "reviewed": 8, "share": 0.25}]}]

    key = nav_env.openrouter_key() if args.llm else None

    print(f"campaign {tpl['campaign']}  |  {args.vertical}  |  mirror: {BODIES}")
    print("PREVIEW ONLY — nothing is sent, no CRM is touched.\n")

    for lead in leads:
        block, meta = lina_compose.compose_block(
            vkey, lead.get("pain_line") or "", key=key,
            pain_summary=lead.get("pain_summary") or "", pains=lead.get("pains") or None)
        subj_raw, smeta = lina_compose.generate_subject(
            vkey, lead.get("pains") or None, key or "", lead.get("pain_summary") or "")
        subject, body = render(tpl["body"], subj_raw, lead, block)
        print("=" * 78)
        print(f"TO      : {lead.get('email') or '(no email — Snov would skip)'}")
        print(f"SUBJECT : {subject}"
              + ("  [generated]" if smeta.get("generated") else f"  [floor: {smeta.get('reason')}]"))
        print(f"BLOCK   : {'generated' if meta.get('generated') else 'library fallback'}"
              + (f" | solutions_used={meta.get('solutions_used')}"
                 if meta.get("solutions_used") else ""))
        print("-" * 78)
        print(body)
        print("-" * 78)
        print("+ PDF attached by Snov, + your signature appended by Snov "
              "(neither is visible here)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Send the Touch-1 EMAIL to leads that already got WhatsApp but had no address at the time.

outreach.py only ever picks up leadStatus="Not Contacted", so once a lead is WhatsApped it
can never receive the email half of its Touch-1 — even after enrichment finds an address.
That is exactly the state the Crawl4AI enrichment creates (2026-07-19: 7 leads gained an
address only after the browser-rendered crawl reached pages plain HTTP got 403 on).

Renders locally and deterministically through the same outreach.render_lead path, so the
copy is byte-identical to what the render file shows, then hands ONE cloud task to Tariq
with every payload spelled out (batched deliberately: the cloud key is metered, and one
task is far cheaper than one per lead).

Usage:
    python scripts/send_email_followup.py --dry-run
    python scripts/send_email_followup.py
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import nav_env
import outreach
import pipeline_prep as prep
from navaia_forge import NavaiaForgeClient
from submit_lead_batch import resolve_agent

ACTIVE = ["Real Estate", "Contracting & Facilities", "Training Institutes"]


def collect() -> list[dict]:
    """WhatsApped leads in active verticals that now HAVE an address."""
    out = []
    for p in prep._crm_people():
        if p.get("sector") not in ACTIVE or p.get("leadStatus") != "WhatsApped":
            continue
        email = (p.get("emails") or {}).get("primaryEmail") or ""
        if not email:
            continue
        # Same check outreach.py makes. This script is a SECOND send path that reads the
        # CRM address directly, so the guard added there on 2026-07-21 did not cover it —
        # a portal mailbox sitting in the CRM would be mailed the moment the lead's status
        # flipped to WhatsApped. A guard at one choke point is not a fence.
        site = ((p.get("company") or {}).get("domainName") or {}).get("primaryLinkUrl") or ""
        if not prep.email_belongs_to(email, site):
            print(f"  SKIPPED {((p.get('company') or {}).get('name') or '')[:40]}: "
                  f"{email} is a third party's mailbox (site {site or '-'})")
            continue
        name = " ".join(x for x in [(p.get("name") or {}).get("firstName"),
                                    (p.get("name") or {}).get("lastName")] if x).strip()
        company = (p.get("company") or {}).get("name") or name
        phone = (p.get("phones") or {}).get("primaryPhoneNumber") or ""
        out.append({
            "person_id": p["id"], "company": company,
            "contact_name": name if name != company else "",
            "sector": p["sector"], "email": email, "phone": phone,
            "website": ((p.get("company") or {}).get("domainName") or {}).get("primaryLinkUrl") or "",
            "pain_line": prep.scrape_pain_index().get(prep._phone9(phone), ""),
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    key = nav_env.env("OPENROUTER_API_KEY")
    leads = collect()
    if not leads:
        print("No WhatsApped leads with an address — nothing to send.")
        return

    rendered = [outreach.render_lead(l, True, key) for l in leads]
    rendered = [r for r in rendered if r.get("email_subject")]

    print(f"{len(rendered)} email(s) to send:\n")
    for i, r in enumerate(rendered, 1):
        body_txt = re.sub(r"<[^>]+>", "", r["email_body"] or "").strip()
        print(f"{i}. {r['company'][:38]:38} -> {r['email']}")
        print(f"   sector : {r['sector']}  | pain: {r['pain_source']}")
        print(f"   subject: {r['email_subject']}")
        print(f"   body   : {body_txt[:150]}…\n")

    if args.dry_run:
        print("DRY RUN — nothing sent.")
        return

    payload = [{"person_id": r["person_id"], "to": r["email"],
                "subject": r["email_subject"], "body_html": r["email_body"]}
               for r in rendered]

    desc = f"""Send {len(payload)} Touch-1 EMAILS via the Zoho integration. Email ONLY — these leads
already received WhatsApp; do NOT send any WhatsApp message.

For each item below: send to `to`, with `subject` and `body_html` EXACTLY as given, verbatim.
Do not rewrite, translate, shorten, or add a signature (the Zoho domain signature is appended
server-side). Do not look anything up in the CRM. Do not message anyone not listed here.

```json
{json.dumps(payload, ensure_ascii=False, indent=1)}
```

After each send, output ONE line in EXACTLY this format (this is parsed programmatically —
a missing line means the lead's CRM status cannot be confirmed and it may be messaged twice):
RESULT | <person_id> | wa=skipped | email=<sent|failed:reason>

Then a short summary of sent/failed counts. Do not fake success. End with [DONE]."""

    cloud = NavaiaForgeClient(api_key=nav_env.env("BUSINESS_NF"), base_url=nav_env.base_url())
    tariq = resolve_agent(cloud, "Tariq")
    t = cloud.tasks.create(nav_env.CLOUD_WORKFORCE_ID,
                           f"SEND (script-approved) Touch-1 EMAIL follow-up ({len(payload)} leads)",
                           description=desc, agent_id=tariq, priority="high",
                           metadata={"kind": "script_authority_email_followup"})
    print(f"✓ task {t.id} ({len(payload)} emails)\nWatching…")

    deadline = time.time() + 900
    while time.time() < deadline:
        time.sleep(20)
        f = cloud.tasks.get(t.id)
        s = str(f.status).lower()
        if s in ("done", "failed", "cancelled", "waiting_blocked", "waiting_question"):
            print(f"\n===== {s.upper()} =====")
            report = f.result or ""
            print(report[:2000])
            if s == "done":
                ok, fail = outreach.apply_crm_updates(report, [p["person_id"] for p in payload])
                print(f"CRM updates: {ok} ok, {fail} failed")
            return
    print("Still running after 15 min — check the dashboard.")


if __name__ == "__main__":
    main()

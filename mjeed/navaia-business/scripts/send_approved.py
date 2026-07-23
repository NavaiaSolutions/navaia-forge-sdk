#!/usr/bin/env python3
"""Send the operator-APPROVED Touch-1 renders by creating DIRECT send tasks for Tariq.

Why this exists (2026-07-14): the three per-vertical outreach tasks rendered their
messages and the operator approved every gate, but the tasks loop — on each resume they
re-render and re-ask instead of proceeding (their descriptions predate the RESUME RULE
fix in submit_lead_batch.py). This script bypasses the loop deterministically:

  1. fetches each gated task's APPROVED render (the exact text the operator saw),
  2. embeds it VERBATIM into a direct SEND task for Tariq (no routing → no 12k
     truncation; the proven pattern of the morning SEND-WA tasks),
  3. after creating the send tasks, rejects the looping gate tasks (superseded).

RUN THIS YOURSELF — creating send tasks is the operator's action:

    .venv/Scripts/python.exe scripts/send_approved.py            # interactive confirm
    .venv/Scripts/python.exe scripts/send_approved.py --dry-run  # print, create nothing
"""
from __future__ import annotations

import argparse
import io
import sys
import os
import time

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nav_env
import pipeline_prep as prep
from navaia_forge import NavaiaForgeClient
from submit_lead_batch import resolve_agent

# The three per-vertical gate tasks the operator approved on 2026-07-14.
APPROVED_GATES = {
    "Real Estate": "5422527c-bf0b-421f-99b8-26e85bde9693",
    "Contracting & Facilities": "dabed971-4b8a-4356-851f-4f34f9e71e48",
    "Training Institutes": "1b1146b2-de31-4920-a1b8-1d758c693f10",
}
# Out-of-scope leads the doctrine excludes (matched as substrings of the company name).
SKIP_LEADS = ["Carpenter Shop"]


def build_send_description(vertical: str, render: str) -> str:
    wa = prep.wa_templates()[vertical]
    skips = "\n".join(f"- {s}" for s in SKIP_LEADS)
    return f"""## SEND the operator-APPROVED Touch-1 messages below — {vertical}

The messages in the APPROVED RENDER at the bottom were reviewed and APPROVED by the
operator (Abdulmajeed) on the original gate task. DO NOT ask for approval again — this
task IS the post-approval send step. Do not re-render, do not alter one character of any
fixed template text.

## WHAT TO DO, PER LEAD in the render
1. WHATSAPP (every lead with a phone): send the Meta-approved template `{wa['name']}`
   via Baian with variables {{{{1}}}}–{{{{5}}}} taken from that lead's rendered message
   (or token table): {{{{1}}}} greeting name-part, {{{{2}}}} pain block paragraph,
   {{{{3}}}} company name, {{{{4}}}} https://cal.com/abdulmajeed-alwardi,
   {{{{5}}}} عبدالمجيد الوردي. The fixed text comes from the template itself.
   Phone format: international, Saudi — prefix 966 and drop any leading 0
   (e.g. 112350077 → 966112350077, 0501234567 → 966501234567).
   If Baian's tool errors (e.g. Graph API 404 on a phone-number id), use the PROVEN
   direct-Graph fallback — never trust a cached id: read env NF_BAIAN_WABA_ID +
   NF_BAIAN_META_TOKEN, DISCOVER the phone number id via
   GET https://graph.facebook.com/v24.0/{{{{WABA_ID}}}}/phone_numbers, then POST
   …/{{{{PHONE_NUMBER_ID}}}}/messages with the template payload. If BOTH fail, record
   the exact error for that lead and continue — no retry loops.
2. EMAIL (only leads whose render includes a real email + rendered email): send via
   Snov.io campaign through the connected Zoho mailbox (ops@navaia.sa), subject and body
   exactly as rendered. Snov auto-appends the signature — the body must carry none.
3. SKIP these leads entirely (out of scope, operator-excluded):
{skips}
4. After each lead's send(s): update that person's leadStatus via the Twenty CRM tool
   (person_id is in the render): "Emailed" if an email went out (wins), else
   "WhatsApped". If the CRM tool is unavailable, list person_id + intended status in
   the report — exactly.

## REPORT (final result), then END with [DONE]
Per lead: company | WhatsApp sent? | email sent? | leadStatus updated? | error verbatim
if any. Then flat totals. End the output with the literal marker [DONE] on its own line.
NEVER end with a question — there is nothing left to ask; every decision above is final.

---

## APPROVED RENDER ({vertical}) — the operator saw and approved EXACTLY this
{render}
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print summaries, create nothing")
    ap.add_argument("--yes", action="store_true",
                    help="skip the interactive confirm (operator already said to run)")
    args = ap.parse_args()

    cloud = NavaiaForgeClient(api_key=nav_env.env("BUSINESS_NF"), base_url=nav_env.base_url())
    h = cloud.tasks._http
    tariq = resolve_agent(cloud, "Tariq")

    plans = []
    for vertical, gate_id in APPROVED_GATES.items():
        gate = h.get(f"/tasks/{gate_id}")
        render = (gate.get("result") or "").strip()
        if not render:
            print(f"!! {vertical}: gate task {gate_id[:8]} has no render — skipping")
            continue
        desc = build_send_description(vertical, render)
        plans.append((vertical, gate_id, desc))
        print(f"{vertical}: render {len(render)} chars -> send-task description {len(desc)} chars")

    if not plans:
        raise SystemExit("Nothing to send.")
    if args.dry_run:
        print("\nDRY RUN — no tasks created.")
        return

    print(f"\nThis creates {len(plans)} SEND task(s) for Tariq — REAL WhatsApp + email outreach.")
    if not args.yes and input("Proceed? (yes/N) ").strip().lower() != "yes":
        print("Aborted — nothing created.")
        return

    created = []
    for vertical, gate_id, desc in plans:
        t = cloud.tasks.create(
            nav_env.CLOUD_WORKFORCE_ID,
            f"SEND approved Touch-1 — {vertical} (operator-approved, no gate)",
            description=desc, agent_id=tariq, priority="high",
            metadata={"kind": "approved_send", "vertical": vertical,
                      "source_gate_task": gate_id},
        )
        created.append((vertical, t.id))
        print(f"  ✓ {vertical}: SEND task {t.id}")
        # Close the superseded looping gate task (it is parked in waiting_question;
        # reject on a non-running task sticks).
        try:
            cloud.tasks.reject(gate_id, "Superseded: approved render handed to Tariq "
                                        f"directly as send task {t.id} (gate loop workaround).")
            print(f"    gate task {gate_id[:8]} closed")
        except Exception as e:
            print(f"    (gate task {gate_id[:8]} not closed: {e})")

    print("\nWatching sends (Ctrl+C to stop; tasks keep running in the cloud)…")
    pending = dict(created)
    while pending:
        time.sleep(20)
        for vertical, tid in list(pending.items()):
            t = cloud.tasks.get(tid)
            s = str(t.status).lower()
            if s in ("done", "failed", "cancelled", "waiting_blocked", "waiting_question"):
                print(f"\n=== {vertical}: {s.upper()} ===")
                print((t.result or "(no result)")[:3000])
                del pending[vertical]
    print("\nAll send tasks finished.")


if __name__ == "__main__":
    main()

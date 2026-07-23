#!/usr/bin/env python3
"""
Submit ONE lead-pipeline batch task to the cloud workforce (Tariq), carrying
pre-scraped leads with it. Generic + repeatable: it tracks which leads have
already been dispatched (a `submitted_task` field written back into the leads
file), so running it again naturally works through the whole pool batch by
batch until every lead is sent.

Flow per batch: qualify -> import to Twenty CRM (native tool) -> Snov enrich ->
Lina copy -> HARD STOP at the channel-agnostic HITL gate -> send on approval.

The scrape itself runs on a laptop (cloud runtime has no browser):
  1. docker run ... gosom/google-maps-scraper:latest-rod ...   (see playbook)
  2. python scripts/distill_scraped_leads.py <scraped.csv> leads_scraped_compact.json
  3. python scripts/submit_lead_batch.py            # first batch
  4. python scripts/submit_lead_batch.py            # next batch (skips submitted)

Usage:
    python scripts/submit_lead_batch.py [--per-vertical 15]
        [--verticals "Real Estate,Contracting & Facilities"]
        [--leads-file leads_scraped_compact.json] [--dry-run]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from datetime import date

# Guarded: run_pipeline.py imports this module and has already wrapped stdout —
# wrapping twice orphans the first wrapper, which closes the stream on GC.
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nav_env
from navaia_forge import NavaiaForgeClient

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
# Batches go to AHMED (GM): direct-to-Tariq bypassed orchestration on the first run
# (task b0c6485b, 2026-07-14) — Tariq couldn't hand off to Lina and ended the task
# with questions in the result instead of a waiting HITL state.
ASSIGNEE = "Ahmed"


def resolve_agent(cloud, name: str) -> str:
    agents = {a.name: a.id for a in cloud.agents.list(workforce_id=nav_env.CLOUD_WORKFORCE_ID)}
    if name not in agents:
        raise SystemExit(f"No cloud agent named {name!r}; roster: {list(agents)}")
    return agents[name]

# CRM sector value -> fallback Overpass/OSM guidance only; search terms live with the scrape.
# ACTIVE verticals — locked to three by operator decision 2026-07-19.
# "Private Clinics" and "Finance & Debt Collection" are RETIRED: never scrape,
# score, import, render copy for, or send to them. Only the operator reopens one.
ALL_VERTICALS = [
    "Contracting & Facilities",
    "Real Estate",
    "Training Institutes",
]

RETIRED_VERTICALS = [
    "Finance & Debt Collection",
    "Private Clinics",
]


def templates_block(verticals: list[str]) -> str:
    """The approved Touch-1 copy for both channels, embedded VERBATIM so copy is
    fill-in-the-tokens, never improvised (first cloud run improvised off-doctrine copy)."""
    import pipeline_prep as prep
    et, wt = prep.email_touch1_templates(), prep.wa_templates()
    parts = ["## APPROVED TEMPLATES (VERBATIM — fill tokens ONLY, change nothing else)"]
    for v in verticals:
        parts.append(f"\n### EMAIL Touch-1 — {v}\n\n{et[v]}")
        w = wt[v]
        parts.append(f"\n### WHATSAPP Touch-1 — {v} (Meta template `{w['name']}` — body is "
                     f"APPROVED VERBATIM, only the {{{{n}}}} variables are filled)\n\n```\n{w['body']}\n```")
    parts.append("""
### Token rules (both channels)
- {honorific+name} / {{1}}: e.g. الأستاذ فلان; if NO contact name, use
  "القائمون على <short company name> الكرام" — never a generic personal honorific.
- {lina_pain} / {{2}}: LINA derives the lead's pain from its pain_hints when they map to a
  solvable pain in the vertical; otherwise the vertical's GENERAL pain. For WhatsApp {{2}} it
  is the coupled pain→solution block; it must read naturally in the sentence, and it MUST
  name the automation (…حلول ذكية تتولّى) — the Meta-locked fixed text can't. The coined
  نُؤتمت/تُؤتمت were rejected by the operator; never reintroduce them.
- NEVER CITE REVIEWS in any output: pain_hints only PICK the pain. State it as a known,
  fixable pain with no attribution — never "لاحظت أن مراجعيكم ذكروا", never تقييمات/مراجعات,
  nothing implying we read feedback about them, even when the pain is org-specific.
- {trigger_line}: one sentence stating the picked pain unattributed (e.g. "في مثل عملكم قد
  يتأخّر الردّ على الاتصالات والرسائل في أوقات الذروة"); EMPTY if no usable hint.
  {inbound_context}: always empty.
- {اسم الشركة}/{اسم العيادة}/{اسم المعهد} / {{3}}: the business name.
- {{4}}: https://cal.com/abdulmajeed-alwardi   {{5}}: عبدالمجيد الوردي
- EMAIL: NO signature in the body (Snov auto-appends it); the body ends on the
  question-close + link line. No bullet lists, no "فريق نڤايا".
- NO EM-DASHES (—) or middots (·/•) anywhere in any filled token — an AI tell that
  violates the doctrine. Use Arabic commas (،) instead.
""")
    return "\n".join(parts)


def build_description(picked: list[dict], per_vertical: int, verticals: list[str]) -> str:
    total = len(picked)
    vlist = " / ".join(verticals)
    with_email = sum(1 for l in picked if l.get("email"))

    return f"""## OBJECTIVE
Run the NAVAIA lead pipeline for this batch of {total} pre-scraped leads ({vlist};
target ≈{per_vertical} QUALIFIED per vertical). You (Ahmed) run EVERY phase IN THIS TASK
(qualify, import via your Twenty tool, fill tokens, gate) — do NOT [ROUTE:...] mid-pipeline;
routing completes the task and kills the gate. Only the post-approval send may be routed
(see PHASE 4).

Everything deterministic is ALREADY DONE and travels with this task: emails are pre-enriched
via Snov ({with_email}/{total} leads have one), and the approved Touch-1 templates for BOTH
channels are embedded verbatim below. Your job: qualify → import → fill tokens → GATE → send
→ report. No Snov enrichment calls, no template retrieval, no improvisation.

**CRITICAL**: Stop BEFORE any send and raise the HITL approval gate — the operator reviews
the rendered messages and approves from any channel (Fareegi dashboard, Telegram, …).

## PHASE 1 — QUALIFY + IMPORT (Tariq)
Qualify each pre-scraped lead below, then import the qualified ones to Twenty CRM.

**EXCLUDE (small shops / out of scope):** individual contractors or sole proprietors with no
office; small workshops (ورش صغيرة); corner retail stores; handymen; businesses with no proper
commercial address; carpentry shops posing as contracting firms.
**QUALIFY only:** established companies with a proper Riyadh commercial address, a professional
phone, and a website OR clear signs of a real operation. Fit quality beats raw count — report
honestly if a vertical falls short.

**CRM (use the native Twenty CRM integration tool — never ask for raw tokens):**
- Company: name, domainName {{"primaryLinkUrl": <website>}}, address {{"addressStreet1": …,
  "addressCity": "Riyadh", "addressCountry": "Saudi Arabia"}}, sector (exact vertical name),
  createdBy {{"source": "AGENT", "name": "Mjeed", "context": {{}}}}.
- Person: name, emails {{"primaryEmail": <the lead's pre-enriched email, when present>}},
  phones {{"primaryPhoneNumber": …, "primaryPhoneCountryCode": "SA"}}, sector,
  companyId, leadStatus "Not Contacted", leadSource "Google-Places",
  createdBy {{"source": "AGENT", "name": "Mjeed", "context": {{}}}}.
- The CRM backend dedups — add all qualified, count only what actually landed.

## PHASE 2 — COPY (fill the templates YOURSELF, in THIS task, exactly)
Do NOT route this phase to Lina: a [ROUTE:...] marker would COMPLETE this task and kill the
approval gate — the templates and token rules below are complete, no other agent is needed.
For every imported lead: group by vertical and fill the embedded APPROVED templates below —
EMAIL Touch-1 for every lead that has an email, AND WhatsApp Touch-1 for EVERY lead (each
lead has a phone). Tokens only; the fixed text is untouchable. Copy is produced BEFORE any
send, never improvised at send time.

## PHASE 3 — HITL APPROVAL GATE (HARD STOP, CHANNEL-AGNOSTIC)
Render every message in full — email AND WhatsApp per lead — then END your output with the
literal marker [WAITING:QUESTION] (on its own line, nothing after it) so THIS task actually
ENTERS the waiting_question state and PAUSES. NEVER end with [DONE] while the gate is open:
a "done" task with unanswered questions is a failed gate — nobody gets asked, nothing sends.
The operator may answer from ANY channel — dashboard, Telegram, elsewhere; do not wait on
one specific channel. Proceed ONLY with what he approves; mark the rest Skipped. The same
rule applies to blockers: raise them with [WAITING:QUESTION] (if the operator can answer)
or [WAITING:BLOCKED] (hard external block) — never by ending the task [DONE].

## PHASE 4 — SEND (approved leads only; the sending itself is TARIQ's — you have no send
tools). RESUME RULE: when the transcript already contains the operator's answer to your
gate, the gate is OVER — do NOT re-render, do NOT re-ask, do NOT output [WAITING:QUESTION]
again. Go DIRECTLY to this phase: END your output with a COMPACT SEND MANIFEST followed
by the literal marker [ROUTE:TARIQ] (routing truncates at 12,000 chars — per-lead
one-liners: person_id | company | phone | email-or-"-" | vertical | WA template name |
{{{{1}}}}..{{{{5}}}} values | email token values — NEVER full rendered bodies; Tariq
reconstructs them from the same verbatim templates + these tokens). Send rules for Tariq
(repeat them above the manifest so they travel with the route):
- EMAIL (leads with an email): Snov.io campaign via the connected Zoho mailbox
  (ops@navaia.sa). Snov auto-appends the signature.
- WHATSAPP (EVERY approved lead — all have phones): Baian (cloud-only), using the exact
  Meta-approved template named per vertical below, variables {{{{1}}}}–{{{{5}}}} in order.
  If Baian's tool errors (e.g. Graph API 404 on a phone-number id), use the PROVEN
  direct-Graph fallback — never trust a cached id: read env NF_BAIAN_WABA_ID +
  NF_BAIAN_META_TOKEN, DISCOVER the current phone number id via
  GET https://graph.facebook.com/v24.0/{{WABA_ID}}/phone_numbers, then POST
  …/{{PHONE_NUMBER_ID}}/messages with the template payload. Only if BOTH paths fail,
  record the exact error per lead and continue with email — do not retry-loop.
- leadStatus after send: "Emailed" if an email went out (wins over WhatsApp), else
  "WhatsApped". Log every send to the dashboard.

## PHASE 5 — REPORT (this is the task's final result)
Per vertical: received / qualified (rejected: one line each, with reason) / imported
(actually landed) / emails available / approved / emails sent / WhatsApp sent / errors.
End with the flat totals.

## CONSTRAINTS
1. NEVER invent data — unknown fields stay empty.
2. NEVER send without the operator's HITL approval — hard stop.
3. The CRM is SHARED. Only touch leads created by Mjeed, and EVERY record you create
   (Company AND Person) must carry createdBy {{"source": "AGENT", "name": "Mjeed",
   "context": {{}}}} — after import, verify the new records show under Mjeed and state
   that check's result in the report.
4. All leads are Riyadh region.
5. Work ONLY from the leads embedded below and the CRM. IGNORE any lead files sitting in
   your workspace from earlier runs — they are stale experiments, not this batch.
6. On import, set Person.sector AND Person.leadStatus="Not Contacted" — both fields, always.
7. WhatsApp bodies are Meta-approved VERBATIM — alter one fixed character and Meta rejects
   the send. Fill only the {{{{n}}}} variables.

---

{templates_block(verticals)}

---

## PRE-SCRAPED LEADS (PRIMARY INPUT — emails already enriched)
Scraped from Google Maps; pain_hints are negative-review snippets from the SAME listing
(trust-locked — usable directly for the pain line).

```json
{json.dumps(picked, ensure_ascii=False, indent=1)}
```
"""


def pick_leads(pool: list[dict], verticals: list[str], per_vertical: int) -> list[dict]:
    """Next unsubmitted leads, oversampled ~60% so qualification rejects don't starve the batch."""
    take = max(per_vertical + 5, int(per_vertical * 1.6))
    picked = []
    for sector in verticals:
        avail = [l for l in pool if l.get("sector_guess") == sector and not l.get("submitted_task")]
        picked += avail[:take]
        print(f"{sector}: {len(avail)} unsubmitted, taking {min(take, len(avail))}")
    return picked


def submit_batch(verticals: list[str], per_vertical: int, leads_file: str,
                 dry_run: bool = False) -> str | None:
    """Pick → submit → mark. Returns the task id (None on dry-run)."""
    unknown = [v for v in verticals if v not in ALL_VERTICALS]
    if unknown:
        raise SystemExit(f"Unknown vertical(s) {unknown}; valid: {ALL_VERTICALS}")

    with open(leads_file, encoding="utf-8") as f:
        pool = json.load(f)
    picked = pick_leads(pool, verticals, per_vertical)
    if not picked:
        raise SystemExit("No unsubmitted leads left for these verticals — scrape more or change verticals.")

    if not dry_run:
        # Auto-enrichment via Snov is disabled per operator flow. Leads are submitted as-is.
        pass

    desc = build_description(picked, per_vertical, verticals)
    title = (f"Pipeline batch: {per_vertical}/vertical qualified leads "
             f"({' + '.join(verticals)}) — HITL gate")
    print(f"\nTitle: {title}\nDescription: {len(desc)} chars, {len(picked)} leads embedded")

    if dry_run:
        print("DRY RUN — nothing submitted, nothing marked.")
        return None

    cloud = NavaiaForgeClient(api_key=nav_env.env("BUSINESS_NF"), base_url=nav_env.base_url())
    task = cloud.tasks.create(
        workforce_id=nav_env.CLOUD_WORKFORCE_ID, title=title, description=desc,
        agent_id=resolve_agent(cloud, ASSIGNEE), priority="high",
        metadata={"verticals": verticals, "per_vertical": per_vertical,
                  "leads_embedded": len(picked), "approval_gate": "hitl_any_channel"},
    )
    print(f"\n✓ Task {task.id} submitted ({task.status}).")

    # Mark the dispatched leads so the next run picks up where this one left off.
    picked_keys = {(l["name"], l["phone"]) for l in picked}
    for l in pool:
        if (l["name"], l["phone"]) in picked_keys:
            l["submitted_task"] = task.id
            l["submitted_at"] = date.today().isoformat()
    with open(leads_file, "w", encoding="utf-8") as f:
        json.dump(pool, f, ensure_ascii=False, indent=1)
    print(f"Marked {len(picked_keys)} leads as submitted in {os.path.basename(leads_file)}.")
    print("The task will stop at the HITL gate — approve the rendered messages from any channel.")
    return task.id


def build_outreach_task(verticals: list[str]) -> tuple[str, str] | None:
    """Prep (normalize + enrich CRM) and build the outreach task for leads ALREADY in
    the CRM but never contacted. Returns (title, description), or None if no leads.
    Shared by run_pipeline.py (console) and telegram_workforce_bot.py (phone)."""
    import pipeline_prep as prep
    prep.normalize_crm_people()
    leads = prep.not_contacted_leads(verticals)
    if not leads:
        return None
    with_email = sum(1 for l in leads if l["email"])
    scope = ("ALL five verticals" if len(verticals) == len(ALL_VERTICALS)
             else "ONLY these verticals: " + ", ".join(verticals) +
                  " — leads in other verticals are OUT OF SCOPE for this task, skip them")

    desc = f"""## OBJECTIVE
Send Touch-1 outreach for the {len(leads)} leads EMBEDDED below ({scope}). They are
Mjeed's "Not Contacted" CRM records, selected and verified deterministically BEFORE this
task was created — fields normalized, emails enriched ({with_email}/{len(leads)} have one).

## PIPELINE EXECUTION
Since these leads are already in the CRM and enriched, you must route this task through our standard pipeline:
1. Since no scraping is needed, you (Ahmed) should route directly to Lina.
2. Lina will write the Touch-1 personalized copy for these leads.
3. Lina will route to Tariq (Sender) and Nora (Scorer) in parallel.
4. Tariq will stop at the HITL gate for approval before sending.

DO NOT generate the copy yourself. DO NOT skip the pipeline. Route to Lina to start the process.
End your output with `[route:lina]`.

---

{templates_block(verticals)}

---

## THE LEADS (verified Mjeed's, Not Contacted — the ONLY records in scope)

```json
{json.dumps(leads, ensure_ascii=False, indent=1)}
```
"""
    vtag = "all verticals" if len(verticals) == len(ALL_VERTICALS) else " + ".join(verticals)
    title = f"Outreach: Not Contacted CRM leads ({vtag}) — Lina copy → HITL gate → Tariq send"
    return title, desc


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--per-vertical", type=int, default=15, help="qualified-lead target per vertical (default 15)")
    ap.add_argument("--verticals", default="Real Estate,Contracting & Facilities",
                    help="comma-separated CRM sector names (default: Real Estate,Contracting & Facilities)")
    ap.add_argument("--leads-file", default=os.path.join(ROOT, "leads_scraped_compact.json"))
    ap.add_argument("--dry-run", action="store_true", help="show what would be submitted, write nothing")
    args = ap.parse_args()
    verticals = [v.strip() for v in args.verticals.split(",") if v.strip()]
    submit_batch(verticals, args.per_vertical, args.leads_file, args.dry_run)


if __name__ == "__main__":
    main()

# 09 — Canonical Scripts

## Added 2026-07-08 (outreach ops, agent ops, dedup, triggers)

| Script | Purpose |
|--------|---------|
| `enrich_reviews.py` | **Trust-locked** review enrichment: reads a lead's OWN Google reviews via exact `place_id` + phone match (never a name search), reasons the pain, writes to the exact CRM lead + `leads_reviews.csv`. Feeds `{trigger_line}`. |
| `email_send.py` | Single transactional/test email via Zoho (`--via zoho\|snov`, `--html`, `--signature-file`). Bulk outreach = Snov campaigns (dashboard). |
| `baian_send.py` / `check_baian_templates.py` | WhatsApp send via Baian (cloud-only) / list template approval status. |
| `deploy_agents.py` | Push each agent's `system_prompt` from `agents/*.md` to the cloud (in-place). |
| `set_agent_models.py` | Apply the model/escalation/max_turns cost policy to agents (in-place). |

---


> **`scripts/` was pruned 65 → 29** on 2026-07-06, cleaned again 2026-07-07 (31
> keepers), then **pruned 54 → 28 on 2026-07-14**: deleted the resolved one-off
> fixes (`fix_twenty_url`, `full_review`, `verify_crm_task`, `configure_twenty`,
> `gen_integration_sql`, `check_cloud_integrations`, `fix_runtime`, `check_runtime`),
> the Places-era lead-gen (`fetch_leads`, `create_lead_task`, `leadgen_2vertical`,
> `leadgen_overpass`), superseded task ops (`approve_task`, `monitor_task`,
> `check_task_status`, `reset_task`, `update_csv_task`, `update_task_with_key` —
> all replaced by `run_pipeline.py`), superseded Snov orchestrators (`step2_snov_v2`,
> `step2_snov_verify`), CRM inspection one-offs (`get_crm_schema`, `query_twenty`),
> `check_email_status`, `submit_wa_templates`, `check_wa_status`, and
> `telegram_approval_bridge` (superseded by `telegram_workforce_bot.py`).
>
> **Do not recreate the deleted experiments** — if an endpoint needs probing,
> do it inline. Git history keeps every deleted file.

---

## Operator console (THE entry point)

| Script | Purpose |
|--------|---------|
| `run_pipeline.py` | **Interactive console for the operator — fire and approve without any LLM/CLI.** Menu: (1) fire the next lead batch from the scraped pool → full cloud pipeline; (2) run outreach for CRM leads already imported but Not Contacted; (3) watch/approve any existing task. When a task pauses at the HITL gate it shows the rendered messages in the terminal and delivers your answer via `POST /tasks/{id}/approve {"response": …}` (body required — a bare approve just re-asks). |

## Setup / Runtime

| Script | Purpose |
|--------|---------|
| `setup_db.py` | One-time DB init. Imports every SQLAlchemy model (including `app.scheduler.models`) and runs `create_all`. Cross-platform, no `-e PYTHONPATH=/app` needed. |

## Lead Fetch

| Script | Purpose |
|--------|---------|
| `fetch_leads_osm.py` | Overpass/OSM lead fetcher (free, keyless, endpoint rotation). Same CSV schema. Fallback source — Riyadh coverage is thin. Primary is the self-hosted `gosom/google-maps-scraper` (Docker) — see `playbooks/lead_pipeline.md`. |
| `distill_scraped_leads.py` | Converts a gosom scraper results CSV into compact JSON (`leads_scraped_compact.json`): phone-bearing rows only, sector guess, up to 2 negative-review snippets as trust-locked pain hints. The JSON is the lead pool batches are drawn from. |
| `submit_lead_batch.py` | Submits ONE pipeline batch task to cloud AHMED with pre-scraped leads embedded (qualify → CRM import → Lina fills the EMBEDDED verbatim templates → channel-agnostic HITL gate → send email + WhatsApp). Runs `pipeline_prep.enrich_leads` first so emails travel WITH the task. Marks dispatched leads (`submitted_task`) in the pool file, so rerunning walks through the whole pool batch by batch. Replaces the one-off `submit_gm_pipeline_task.py` (deleted 2026-07-14). |
| `pipeline_prep.py` | The deterministic prep the console runs before any task exists (no LLM): parses the approved Touch-1 email + Meta-approved WhatsApp templates VERBATIM from `04_outreach_templates.md` for embedding; Snov v2 enrichment for pool leads (idempotent, `snov_checked` marker); CRM normalization (missing Person sector/leadStatus) + Snov enrichment for Not Contacted CRM leads. Standalone run = the CRM prep. |

## Clean / Dedup

| Script | Purpose |
|--------|---------|
| `step1_clean.py` | Stage 1 cleaner: address validation, phone regex, domain extraction. |
| `graphql_dedup.py` | English-name dedup vs Twenty CRM via GraphQL. Uses `first` + `after` + `cursor` (REST pagination is broken). |
| `crosslang_dedup.py` | Cross-language (Arabic ↔ English) dedup via transliteration + domain/phone/address overlap. |

## Enrich

| Script | Purpose |
|--------|---------|
| `enrich_emails.py` | Website crawl (homepage + 10 contact paths) + DuckDuckGo search. Found 4 new emails. |
| `fetch_emails_snov.py` | Snov.io v2 email fetcher (start task → poll for results). |

## Verify

| Script | Purpose |
|--------|---------|
| `verify_all_emails.py` | Snov.io v2 email verification for all leads. Updates `leads_enriched.csv` with `email_status`. |
| `verify_import.py` | Post-import verify — GraphQL `totalCount` check vs expected counts. |

## Import

| Script | Purpose |
|--------|---------|
| `import_selected_leads.py` | Import leads to Twenty CRM (person-first, deduped). `--from-pool <enriched.json>` migrates the scrape pool; `--src selected_leads.json` the selection. 0.5s rate limit. (Replaced the broken `import_all_leads.py`, removed 2026-07-20.) |

## CRM Utils

| Script | Purpose |
|--------|---------|
| `dump_crm.py` | Dump all companies + contacts to JSON (the one CRM inspection tool). |

## Checks

| Script | Purpose |
|--------|---------|
| `check_snov_credits.py` | Check Snov.io credit balance. |

## WhatsApp (Baian) — cloud-only

| Script | Purpose |
|--------|---------|
| `baian_send.py` | Send a WhatsApp via Baian: `--to`, `--template`. Creates a cloud task → approves plan → prints `message_id`. See `playbooks/whatsapp_send_baian.md`. |
| `check_baian_templates.py` | Read-only: list Baian templates + Meta approval status (paginates all pages). |
| `manage_wa_templates.py` | Prune/fix the Meta template set via **direct Graph API** (cloud task → Tariq). Modes: `run1` (delete dup + rejected, recreate, sweep superseded/artifacts), `recreate` (create the `_v2` finance/training under the approved realestate structure), `inspect --ids` (GET exact approved bodies), `finalize` (delete `_t1` originals — only after `_v2` APPROVED). |

## Task Ops

> All task operations (create batch, monitor, approve/answer HITL, re-run blocked)
> live in **`run_pipeline.py`** (operator console) + **`submit_lead_batch.py`**
> (scriptable batch submit). The seven single-purpose task scripts were deleted
> 2026-07-14.

---

## Why these scripts exist (context for the scripting model)

The `moonshotai/kimi-k2.6` model via the `navaia` CLI produced malformed JSON
for complex tool calls during the first lead-finding run (bash commands with
multi-line scripts). For reliable data fetching, the pipeline uses **direct
Python scripts** rather than relying on the agent runtime. The agent
orchestrates; the scripts do the work.

This is a deliberate architectural choice documented in §10.8 of the original
spec. **Do not "fix" this by trying to make the agent do the fetching** —
keep the scripts.

---

## Deleted Experiments (do not recreate)

These were deleted on 2026-07-06 per the "useful data upfront, no junk" rule:

| Category | Count | Why deleted |
|----------|-------|-------------|
| `test_*` | many | Throwaway test scripts |
| `debug_*` | several | One-off debugging artifacts |
| `inspect_*` | several | Schema/format inspection one-liners |
| Superseded duplicates | several | Old versions of canonical scripts |
| **Total deleted** | **36** | |

If you need a script that doesn't exist, write it inline (e.g., in a Python
REPL or a one-liner in the shell). Don't add new files to `scripts/` unless
they're a real, reusable pipeline stage.

---

## Pipeline Order (canonical)

**Preferred (cloud-batch, interactive):**
```bash
python scripts/run_pipeline.py     # fire batch / outreach → approve at the HITL gate, all in one console
```

**Local scripted path (manual stages):**
```bash
# 1. Setup (one-time per fresh install)
python scripts/setup_db.py

# 2. Lead fetch — Maps scrape (Docker, primary) or OSM fallback; Places API is retired
python scripts/fetch_leads_osm.py

# 3. Clean
python scripts/step1_clean.py

# 4. Enrich
python scripts/enrich_emails.py
python scripts/fetch_emails_snov.py

# 5. Verify
python scripts/verify_all_emails.py

# 6. Import (person-first, deduped)
python scripts/import_selected_leads.py --from-pool leads_enriched_people.json

# 7. Post-import verify
python scripts/verify_import.py

# 8. Review enrichment (trust-locked)
python scripts/enrich_reviews.py
```

> **No dedup steps.** The Twenty CRM backend handles duplicate elimination automatically — never run agent-side dedup. The dedup scripts (`graphql_dedup.py`, `crosslang_dedup.py`) are kept as manual one-off reconciliation tools only.
>
> **Single source of truth:** Twenty CRM. `leads_enriched.csv` from the initial Phase-1 run is historical reference only.
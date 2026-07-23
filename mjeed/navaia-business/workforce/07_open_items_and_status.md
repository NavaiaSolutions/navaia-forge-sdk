# 07 — Open Items & Status (Done / Blocked / Pending)

> **Snapshot of what's done, what's blocked, and what's pending** as of
> 2026-07-10. This is the authoritative status reference for the workforce.

---

## Done

| Item | Note |
|------|------|
| **Twenty CRM** | Configured locally with token from `.env`. Base URL: `https://crm.navaia.sa`. REST + GraphQL both reachable. |
| **Twenty CRM dedup (English-name match)** | `scripts/graphql_dedup.py` — 48 raw leads → 36 clean. 12 dups removed by name + domain. **Historical (one-off)** — CRM backend now handles dedup automatically. |
| **Twenty CRM cross-language dedup (Arabic ↔ English)** | `scripts/crosslang_dedup.py` — transliteration + domain/phone/address overlap. 0 dups found across all 645 companies. **Historical (one-off)** — CRM backend now handles dedup automatically. |
| **Bulk import to Twenty CRM** | `scripts/import_all_leads.py` — 35 companies + 35 people created (شركة اتقان العقارية imported separately as test). 0.5s rate limit. |
| **Email verification pipeline (Snov.io v2)** | `scripts/verify_all_emails.py`. All 15 verified `.sa` emails return `smtp_status: unknown` — Saudi mail servers don't respond to SMTP probes. Treat as "likely valid, unverified at SMTP layer." |
| **Email enrichment (website crawl + web search)** | `scripts/enrich_emails.py` — homepage + 10 contact paths + DuckDuckGo. Found 4 new emails. |
| **Outreach templates (5 verticals × 3 touches)** | `04_outreach_templates.md` — formal Arabic, field vocab, per-vertical compliance, cal.com CTA, no signature in body (Snov auto-appends the account signature; reference copy `assets/email_signature.html`). Clean PDF: `NAVAIA_Outreach_Templates.pdf`. |
| **Outreach — impact numbers** | Confirmed across verticals: cost −40%, profit +30%. Placeholders replaced in templates. |
| **Lead scoring model** | Designed in `05_lead_scoring_model.md`. Rules-based 0–100 model. Implementation is scripting-model work. |
| **Runtime setup (claw_code runtime + kimi-k2.6)** | Verified via `scripts/check_runtime.py`. |
| **DB init script** | `scripts/setup_db.py` works cross-platform, includes scheduler tables. |
| **SDK fixes** | JWT auth, DEBUG flag, version sync, doc drift — all resolved. |
| **Scripts pruned** | `scripts/` reduced from 65 → 29 (deleted all `test_*`, `debug_*`, `inspect_*`, and superseded duplicates). |
| **Baian (WhatsApp) — VERIFIED LIVE** | Cloud integration **ACTIVE** (`baian.navaia.sa`). Proven end-to-end 2026-07-07: cloud workforce (in `draft`, no activation needed) → Tariq → Baian → Meta template → owner's WhatsApp delivered. Two real messages sent (`meeting_confirmation`, then approved custom `navaia_connectivity_test_v1`). First-contact requires a Meta-**APPROVED** template via `send_template`; new templates approve in ~minutes. |
| **WhatsApp MJ template set — complete (5/5 verticals)** | 2026-07-10: All 5 option-B Touch-1 templates APPROVED — `navaia_mj_clinics_t1`, `navaia_mj_contracting_t1`, `navaia_mj_realestate_t1`, `navaia_mj_finance_t1_v2`, `navaia_mj_training_t1_v2`. Two hard Meta rules learned: (1) no trailing/leading `{{n}}` — needs fixed text after `{{5}}` + an `example`; (2) 30-day name lock after delete. Script refactored to `cleanup` mode (deletes junk in one shot, no recreate). |
| **Cloud-only operation (no local containers)** | 2026-07-13: `scripts/nav_env.py` centralizes backend resolution via `NAVAIA_BASE_URL` (default = cloud `fareegi.navaia.sa`); all acting scripts use it, and the 3 `localhost:8001` scripts (`create_lead_task.py`, `monitor_task.py`, `configure_twenty.py`) were repointed to the cloud workforce. Nothing targets a local Docker stack unless `NAVAIA_BASE_URL` is set explicitly. |
| **Reconstruct-anywhere snapshot** | 2026-07-13: `scripts/workforce_snapshot.py` (`export`/`import`) wraps SDK `client.sync`; committed bundle at `workforce/snapshot/workforce_bundle.json` (7 agents, 15 edges, 1 KB, 7 integrations, secrets redacted). Rebuilds the workforce on any backend. |
| **Runtime switched to Kimi** | 2026-07-13: workforce `runtime_mode` set `claude_max → claw_code` so agents run on their configured model. All 7 agents are `moonshotai/kimi-k2.6` (primary + escalation). Under `claude_max` the Claude CLI ignored the Kimi `model_name` (worker passes `model=agent.model_name` to the runtime — the Claude CLI can't run Kimi); `claw_code` (multi-model CLI) honors it. Applied via `cloud.workforces.update(runtime_mode="claw_code")`, verified by re-fetch. |
| **Twenty CRM integration URL corrected** | 2026-07-13: the cloud `twenty` integration pointed at `navaia-business.twenty.com` where the workspace token is invalid; re-created pointing at `crm.navaia.sa` (`a3f5ac89-…`, confirmed correct with the user). 2026-07-14: the stale record was purged (see next row) — CRM works at runtime. |
| **Cloud-only batch run proven (with caveats) + operator console** | 2026-07-14: with ALL local Docker closed, batch task `b0c6485b` imported 29 leads into the CRM via the native tool — but ended `done` instead of pausing at the HITL gate (questions in result text), bypassed Lina (was assigned direct to Tariq), and left `sector`/`leadStatus` empty on the new People. Counters baked into `submit_lead_batch.py` (assign Ahmed, explicit wait-state demand, ignore-workspace-files, both-fields-on-import). **NEXT STEP: run `scripts/run_pipeline.py` → option 2** (outreach for Not Contacted — includes the normalize step) and approve at the gate. Scripts pruned 54 → 28; `run_pipeline.py` is the operator entry point. |
| **Google Places API retired → free replacement stack** | 2026-07-14: Places is unusable (Google Maps Platform in Saudi requires a CNTXT corporate account we don't have). Replaced at zero cost: **primary** = self-hosted `gosom/google-maps-scraper:latest-rod` (MIT; verified live — 32 places with phones + Arabic reviews from one Riyadh query; reviews feed the trust-locked pain enrichment from the same listing; `latest`/v1.16.x tags are broken upstream — patched build at `deploy/gmaps-scraper/Dockerfile`); **fallback** = Overpass/OSM via new `scripts/fetch_leads_osm.py` (keyless, endpoint rotation; tested — but Riyadh coverage probed at only ~30 phone-bearing SMBs, so supplement only). Docs + agent payloads updated across the repo; `PLACES_API` references killed. |
| **HITL approval made channel-agnostic** | 2026-07-14: per the operator, approval was wrongly framed as Telegram-only. Now: every send is gated on the operator seeing the RENDERED messages and approving via a HITL question on the task (waiting_question) — answerable from ANY channel (Fareegi dashboard, Telegram relay, …). Rewritten in `_shared_preamble.md`, Ahmed/Lina/Tariq payloads, `02_end_to_end_flow.md`, `submit_gm_pipeline_task.py`. **Cloud redeploy of the 7 agents pending** (`scripts/deploy_agents.py`). |
| **Stale integrations purged — runtime CRM restored** | 2026-07-14: Navaia removed the stuck duplicates (`twenty 5961b579-…` and the empty `telegram f3369460-…`). Integration list now shows a single `twenty` (`a3f5ac89-…` → `crm.navaia.sa`) and a single `telegram` (`eb68017e-…`). Verified end-to-end: a read-only CRM probe task to Tariq (`scripts/verify_crm_task.py`) completed — the in-task CRM tool reads `crm.navaia.sa` (200 people returned, ~158 companies referenced). Whether the underlying `/integrations` PUT/DELETE 500 bug was also fixed is unverified — assume it persists until re-tested before the next integration edit. |

---

## Blocked

| Item | Note | Unblock condition |
|------|------|-------------------|
| **Dashboard cannot answer a waiting task (HITL UI gap)** | 2026-07-14, operator-confirmed: the Fareegi dashboard shows a `waiting_question` task but offers NO way to answer it (the chat creates conversations, not task answers). The backend endpoint exists and works (`POST /tasks/{id}/approve {"response": …}`); the UI just never exposes it. Until fixed, the ONLY approval surfaces are our Telegram bot and `scripts/run_pipeline.py` — so hosting the bot (see `NAVAIA_TELEGRAM_REQUEST.md`) is the critical path for phone-only operation. Request drafted: `NAVAIA_DASHBOARD_HITL_REQUEST.md`. | Navaia adds an answer box + approve button on waiting tasks (and a re-run button for `waiting_blocked`). |
| **Agents reading our private repo live (dynamic)** | 2026-07-13: Not self-serviceable on this Fareegi instance — GitHub connect grants only `user:email` scope; no `github` plugin in the registry (`POST /integrations {plugin_name:"github"}` → 400 "not registered"); agent tools need a registered backing plugin. A read-only fine-grained PAT (Contents: Read on `AkiraKh98/navaia-business-workforce`) is the right credential but unusable until the capability exists. | Navaia registers a GitHub integration plugin OR a cloud-runtime GitHub MCP server that accepts a PAT. Request drafted: `NAVAIA_GITHUB_REQUEST.md`. |

---

## Pending (handed to scripting model)

| Item | Note | Spec |
|------|------|------|
| **Outreach — sending / automation** | Lina writes → Tariq sends: merge Lina's copy + CRM leads, apply §11.5 score, send email via **Snov.io campaign → Zoho mailbox**; WhatsApp via **Baian (cloud-only)**. Planning session does NOT do this. | `agents/lina_marketing.md` + `agents/tariq_sdr_lead_fetcher.md` (Outbound Sending) + `04_outreach_templates.md` + `05_lead_scoring_model.md` |
| **Scheduler / pipeline automation** | Design after outreach sending is wired and tested. | TBD |
| **Additional agents** | Explore with user (e.g., inbound-lead-qualifier, meeting-scheduler, analytics). | TBD |

---

## What Still Needs User Input

> All design-blockers for the user are resolved as of 2026-07-07.
> Identity (name, company, cal.com, phone), tone, cadence, channel,
> targeting, impact numbers — all locked.

| Item | Status |
|------|--------|
| User's name | **Resolved** — عبدالمجيد الوردي / Abdulmajeed Alwardi |
| User's company | **Resolved** — نڤايا / NAVAIA |
| User's cal.com | **Resolved** — https://cal.com/abdulmajeed-alwardi |
| User's phone | **Resolved** — `NAVAIA_CONTACT_PHONE` (see .env) |
| Tone | **Resolved** — formal فصحى, direct/brief |
| Cadence | **Resolved** — day 0 / +3 / +7 |
| Channel | **Resolved** — email first, WhatsApp later |
| Targeting | **Resolved** — most-responsive contact, not executive-only |
| Impact numbers | **Resolved** — cost −40%, profit +30% (confirmed across verticals) |

**Nothing pending from the user for the planning phase.**

---

## Resume Checklist (for next session)

If you're picking this up cold:

1. **Read `workforce/README.md`** — orientation
2. **Read `workforce/00_setup_and_runtime.md`** — what's running
3. **Read `workforce/06_pipeline_state.md`** — current data state
4. **Read this file** — what's done/blocked/pending
5. If scripting model: start with the sending automation
6. If planning model: hand off to scripting model

---

## Risk Register

| Risk | Mitigation |
|------|------------|
| Snov.io credits run out | 805 balance, resets in ~18 days. Watch with `scripts/check_snov_credits.py`. |
| Snov.io `.sa` SMTP returns unknown | Accept "likely valid" — Saudi servers don't respond to probes. |
| Zoho sending domain not warmed | Ramp slowly: 20/day → 50/day over 1 week. |
| Baian token lives only on cloud | Token is in the cloud integration config (redacted locally, no local backup). Baian tasks MUST run on the cloud runtime; never expect a local `BAIAN_TOKEN`. |
| Twenty CRM pagination via REST broken | Always use GraphQL for reads across pages. |
| Container env vars not passed | Only `OPENROUTER_API_KEY` is in container env. Other vars must be embedded in task descriptions or added to `docker-compose.yml`. |
| Agent model produces malformed JSON for complex tool calls | Fall back to direct Python scripts (see `09_canonical_scripts.md`). |
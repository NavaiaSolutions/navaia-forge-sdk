# 08 — Change Log

> Chronological record of all decisions, fixes, and milestones for the
> NAVAIA Business workforce. Reconstructed from git history + the runtime
> scripts in `scripts/`.

---

## 2026-07-19

- **PIPELINE FIXED: routing collision resolved, chain walkable end-to-end, fabricated leads
  purged.** The chain had been broken since 75744c8 by three mutually contradictory pipeline
  definitions. Root causes found and fixed:

  1. **Duplicate scraper role.** `ghida_creative.md` AND `rashid_scraper.md` both defined a
     "Scraper & Importer". Resolved per operator: **Rashid owns scraping**; Ghida restored to
     Creative Director (visual identity / RTL layout, out of the outreach chain).
  2. **Case-sensitive routing failure.** Ahmed's prompt emitted `[ROUTE:RASHID]` (uppercase)
     while edges match `contains:[route:rashid]` literally. The marker matched nothing and
     failed **silently** — no error, no operator notice.
  3. **Missing edge.** Rashid was told to end with `[route:lina]`, but no `Rashid→Lina` edge
     existed; his only outbound was `Rashid→Ahmed`. Dead end. Created the real edge
     **`Rashid→Nora`** (`bc709de4`, `contains:[route:nora]`) — chain now 19 edges.
  4. **Nora was a dead end.** Her prompt said receive-from-Lina, report, `[DONE]`, never route
     — and she performed no CRM import despite owning the only CRM write. Rewritten: receives
     from Rashid → scores → imports → `[route:lina]`.
  5. **Tariq closed the chain early.** Ended with `[DONE]` after sending, so Ahmed never
     aggregated. Now ends `[route:ahmed]`. HITL gate hardened: printing the manifest above a
     `[DONE]` is called out as a FAILED gate.

- **Consequence of the above (the reason this mattered):** with every route silently dead,
  Ahmed looped — restating "I am Ahmed, I do not perform scraping work myself" five times —
  then **fabricated two companies and two contacts and wrote them into the production CRM**
  ("Al Rajhi Financial Solutions"/`alrajhifs.com`, "Riyadh Debt Recovery Partners"/`rdrp.sa`,
  with invented emails and phones). Evidence: `ahmed_hallucination.txt`. All 4 records were
  **verified live in `crm.navaia.sa` and deleted** (confirmed 404 after delete). Had the send
  step run, real outreach would have gone to addresses that do not exist.

- **New standing guards in `_shared_preamble.md`** (ships to all 7 agents):
  `<never_fabricate>` — invented lead data is the workforce's worst failure; a tool failure
  means report the exact error and end `[WAITING:BLOCKED]`, never substitute plausible data,
  never route a fabricated batch onward. Zero honest leads is a success.
  `<stay_in_role>` — silence after routing is EXPECTED (routing spawns an unobservable task);
  never re-emit a marker, never "act as" another agent, never loop restating your role.
  Routing section now states the marker is lowercase and case-sensitive, lists all 19 real
  edges, and warns edges fire once per chain.

- **Deployed + synced:** all 7 prompts pushed via `deploy_agents.py` (verified by re-fetch);
  stale cloud `role` fields corrected (Rashid `Head of Strategy & Intelligence`→`Lead Scraper`,
  Nora `Finance Manager`→`Lead Scorer & CRM Importer`, Tariq→`SDR / Outreach Sender`);
  snapshot bundle re-exported from live.

  **Canonical chain:** Ahmed —`[route:rashid]`→ Rashid —`[route:nora]`→ Nora —`[route:lina]`→
  Lina —`[route:tariq]`→ Tariq —(HITL `[WAITING:QUESTION]`)→ —`[route:ahmed]`→ Ahmed `[DONE]`

---

## 2026-07-14

- **FIRST REAL BATCH OUTREACH SENT — 30 WhatsApp + 20 emails, 0 send errors.** Per-vertical
  gates (13 Real Estate / 8 Contracting / 10 Training) rendered by Ahmed, operator-approved,
  executed by Tariq: WhatsApp via Meta templates through the direct-Graph fallback (Baian's
  cached phone-number id 404s every time — the fallback discovered id `938243176048092` and
  is effectively the primary path), emails via Snov campaigns (ids 3074238-43+). "Carpenter
  Shop" skipped (out of scope). CRM leadStatus: RE updated in-task via Twenty GraphQL; the
  contracting/training runs hit `crm.update NEEDS_KEY` (in-task CRM tool availability is
  FLAKY per-run despite the 07-14 probe passing) → the 17 pending updates were applied
  locally via `PATCH crm.navaia.sa/rest/people/{id}` (all 30 leads now Emailed/WhatsApped).
  Operational learnings baked into scripts: (1) approved gate tasks LOOP on resume if their
  description predates the RESUME RULE (re-render + re-ask after every approval — 4 wasted
  approvals) → `scripts/send_approved.py` bypasses by handing the approved render verbatim
  to Tariq as a direct send task; task templates + console approve-text now carry the
  RESUME RULE; (2) `tasks.reject` does NOT stop an already-executing run (the cancelled
  typo-template task finished and routed to Tariq — harmless: that routed run had no tools
  and no lead data); (3) console gained option 4 "approve ALL waiting gates" (caution: it
  sweeps EVERY waiting task — read the list); (4) a 31-lead render exceeds the ~18k output
  cap and dies signal-less → outreach fires per-vertical now; (5) contracting WA template
  switched to `navaia_mj_contracting_t1_v2` (id 859187770325647, approved 2026-07-14) —
  the old `_t1`'s locked body has the brand typo فريق نفايا; never send with it.
- **Routing made deterministic + the runtime signal contract shipped to all 7 agents.**
  Root causes found for the day's two pipeline breaks: (1) tasks froze `pending` 13:12–14:32Z
  because the cloud's OpenRouter key has a **rolling-24h $4 cap** (`limit_reset: daily`) that the
  morning runs exhausted — `navaia_code` tasks stall silently (no logs) when LLM calls fail; the
  key's account is nearly drained and the workforce provider key is **dashboard-only** (the API
  `PUT /workforces/{id} {"provider_key"}` returns 200 but silently ignores it). (2) A completed
  outreach task (`ba5a3623`) auto-routed to **Rashid** because default edge routing is
  `"mention"` — a substring search of the target agent's NAME in the result — and a lead was
  named "Al Rashid Trading & Contracting Co.". Fixes applied: all **15 edges** now carry
  `condition_expr = contains:[route:<agent>]` (verified persisted) so routing fires only on a
  deliberate literal `[ROUTE:NAME]` marker; `_shared_preamble.md` gained `<runtime_signals>`
  documenting the end-of-output contract (`[DONE]` / `[WAITING:QUESTION]` for every HITL gate /
  `[WAITING:BLOCKED]` / `[ROUTE:NAME]`, + the 12k-char route-truncation warning) — previously the
  agents were ordered to "enter waiting_question" without ever being told the marker that does
  it, which is why Ahmed printed the gate as text and signaled DONE; Ahmed's payload now spells
  out route-vs-in-task work (fill embedded templates himself when the task says so — delegation
  tools don't exist in the task runtime; `[ROUTE:LINA]`/`[ROUTE:TARIQ]` only at task end, compact
  payloads). Deployed via `deploy_agents.py` (all 7 verified). Dead mis-routed task `c6237c74`
  rejected. **Open:** operator must put his own OpenRouter key into the Fareegi dashboard
  (`MY_OPENROUTER_KEY` in `.env`) before the next batch — old key has <$2 left.
- **First cloud-only batch run (task `b0c6485b`) — Phase 1 landed, orchestration gaps found.**
  Proof sequence: scraped 175 phone-bearing leads locally (gosom `latest-rod`, 5 Arabic queries),
  distilled to `leads_scraped_compact.json`, closed EVERY local container + Docker Desktop, then
  submitted the batch (50 embedded leads) purely over HTTPS. Result: Tariq imported **29 people
  + companies** via the native CRM tool (1 CRM-deduped) — the cloud can run the pipeline with no
  local infra. Gaps: (1) task was assigned DIRECT to Tariq, bypassing Ahmed — Tariq couldn't hand
  off to Lina ("who is Lina?"); (2) instead of ENTERING waiting_question at the gate, the run
  ended `done` with its questions in the result text — a failed gate mechanically, though nothing
  was sent; (3) mid-run tool flakiness sent Tariq into STALE workspace lead files from a 07-13
  experiment (roshn/neom emails — not our data); (4) imported People were missing `sector` +
  `leadStatus`. All four are now countered in the batch-task template (`submit_lead_batch.py`):
  assignee = Ahmed, "enter the waiting state — never end done with open questions", "ignore
  workspace files", "set sector + leadStatus on import". Outreach for the imported leads runs as
  a follow-up task (console option 2, includes a normalize step).
- **Pipeline made "fire → approve → report" (operator decision) + WhatsApp for every number.**
  Root causes of the manual babysitting were removed by moving everything deterministic OUT of
  the cloud task and into local prep (`scripts/pipeline_prep.py`, run automatically by the
  console): (1) Snov email enrichment now happens BEFORE submit and the emails travel with the
  task (in-task Snov flaked on run 1); (2) missing CRM fields are normalized locally (the 29
  imported people were fixed: sector + leadStatus set); (3) the approved Touch-1 EMAIL template
  AND the Meta-approved WhatsApp body (verbatim, per vertical) are EMBEDDED in every task — copy
  is fill-in-the-tokens, never improvised (run 2 improvised off-doctrine copy). Task flow now:
  qualify → import (createdBy=Mjeed enforced + verified in the report — CRM is shared) → Lina
  fills tokens → HITL gate (both channels rendered) → send: Snov email for every lead WITH an
  email + Baian WhatsApp Touch-1 for EVERY lead (operator wants both; leadStatus "Emailed" wins
  over "WhatsApped") → per-vertical report. The off-template outreach task (e3cd5b04) was
  cancelled and superseded by this flow.
- **Scripts pruned 54 → 28 + ONE operator console.** New `scripts/run_pipeline.py`: interactive,
  no LLM/CLI — fire the next batch (or outreach-for-existing), watch the task, and ANSWER its
  HITL gate from the terminal (POST approve `{"response": …}`). `submit_lead_batch.py` refactored
  into importable functions (used by the console); `submit_gm_pipeline_task.py` and 25 other
  one-off/superseded scripts deleted (list in `09_canonical_scripts.md`).
- **Google Places API retired; zero-cost lead-gen stack in its place.** Places now requires a
  CNTXT corporate account in Saudi (no access). New primary: self-hosted open-source
  `gosom/google-maps-scraper` — **use the `latest-rod` image tag** (verified live: one Arabic
  Riyadh query → 32 places with phone, address, rating, place_id, and full Arabic user reviews;
  the reviews arrive with the listing itself, preserving the trust-locked pain enrichment).
  The plain `latest`/v1.16.x tags + Windows binary are broken upstream (Playwright driver bug,
  gosom issue #302) — a locally patched build lives at `deploy/gmaps-scraper/Dockerfile`.
  New fallback: `scripts/fetch_leads_osm.py` (Overpass/OSM, keyless, endpoint rotation, same
  CSV schema) — works, but a coverage probe found only ~30 phone-bearing in-vertical SMBs in
  the Riyadh bbox, so OSM is a supplement, not a batch-filler. Rejected: Wathq (Ministry of
  Commerce API — corporate-oriented, 100-query trial then paid); free-tier hosted POI APIs
  (Geoapify/LocationIQ/HERE) — mostly OSM-backed, same thin Riyadh data. Docs updated:
  `06`, `09`, `10`, `02`, `playbooks/lead_pipeline.md`, `tasks/lead_fetch.md`, agent files.
- **HITL approval gate made channel-agnostic (operator decision).** Approval = the operator
  SEEING the rendered messages and answering the task's HITL question — from any channel
  (Fareegi dashboard, Telegram relay, anywhere); never Telegram-only, never blocked on one
  channel. Rewritten in `_shared_preamble.md` (ships 7×), Ahmed's rules + standing pipeline,
  Lina's constraints, Tariq's send/examples, `02_end_to_end_flow.md` (gate added to the happy
  path + handoff map), `submit_gm_pipeline_task.py` (Phase 4). Agent redeploy pending.
- **`submit_gm_pipeline_task.py` no longer embeds TWENTY_TOKEN or PLACES_API.** CRM auth =
  the native `twenty` integration tool; Places key is dead. Snov creds still embedded (native
  snov tool not yet verified in-task).
- **Telegram bot can now FIRE the pipeline (phone-only operation).** New 🚀 menu: 📦 new
  lead batch and 📣 outreach-for-existing run the SAME prep + task builders as the console
  (`submit_lead_batch.submit_batch` / new shared `build_outreach_task`) inside the bot
  container in a background thread, submit to Ahmed, and the HITL gate arrives as the bot's
  existing ✍️ Answer card — start → approve → report without any laptop. Image now ships the
  pipeline toolkit (pipeline_prep, submit_lead_batch, lina_compose, 04 templates, a lead-pool
  snapshot) with a volume-backed pool (`LEADS_FILE=/app/data/…`) so batch markers survive
  rebuilds; bot env adds SNOV creds. Host-agnostic: same image runs on the laptop today and
  on Navaia's in-Kingdom host (request pending). Laptop remains only for pool refills
  (browser scrape) and prompt/doc maintenance.
- **Telegram bot: company cache removed → live per-lead CRM lookup.** The bot no longer
  bulk-loads Mjeed's companies into memory at startup (`load_companies`/`_company_cache`
  deleted); approval cards now call `lookup_company(name)` — a single-company GraphQL query
  (`filter {name:{ilike:…}}`, verified live) at card-render time, filtered to Mjeed's records.
  Always-fresh data, nothing held in memory (tighter PDPL posture), same card content.
  Also fixed the same day: the laptop `navaia-tg-bot` container was crash-looping on
  `api.telegram.org` DNS. Real root cause (after ruling out the compose network): the
  **laptop ISP's resolver filters api.telegram.org** (NXDOMAIN; 8.8.8.8 / 1.1.1.1 resolve it
  fine), and containers inherit the host resolver. Fix in `deploy/telegram-bot/docker-compose.yml`:
  `network_mode: bridge` + pinned `dns: [8.8.8.8, 1.1.1.1]`.
- **Runtime CRM restored — stale integrations purged by Navaia.** The stuck duplicates
  (`twenty 5961b579-…` pointing at the wrong `navaia-business.twenty.com`, and the empty
  `telegram f3369460-…`) are gone; the integration list now has a single `twenty`
  (`a3f5ac89-…` → `crm.navaia.sa`) and a single `telegram` (`eb68017e-…`). Verified
  end-to-end with the read-only probe (`scripts/verify_crm_task.py`): Tariq's in-task
  CRM tool now reads `crm.navaia.sa` successfully (200 people returned, ~158 companies
  referenced) — the 2026-07-13 `401 WORKSPACE_NOT_FOUND` blocker is resolved. Whether
  the underlying `/integrations` PUT/DELETE 500 bug was also fixed is unverified;
  re-test before the next integration edit. `07_open_items_and_status.md` updated
  (Blocked row removed → Done).

## 2026-07-13

- **Email signature: Snov now auto-appends the account signature — body stays signature-free.**
  Snov.io send is live (confirmed: `email_send.py --via snov` created campaign `3071918` /
  list `40232666` and queued a send). A test to the user's inbox proved Snov **auto-appends the
  account's configured HTML signature** and renders it as a branded block. An embed experiment
  (adding `{signature}` to each touch body) **double-stamped** the signature, so it was reverted:
  bodies carry **no signature**, and Snov sends must **not** pass `--signature-file`. Docs
  reconciled to this (`04_outreach_templates.md`, `lina_marketing.md` [dropped the stale 4-line
  plain-text block], `email_send_snov.md`, `03_outreach_strategy.md`, `07_open_items_and_status.md`).
  Reworked `assets/email_signature.html` off the user's clean base (fixed 3px purple left-border
  table, inline styles, no fragile fractional widths) as the **reference copy** of the Snov
  signature. **Resolved 2026-07-14:** the Snov live signature now matches the asset —
  `sig_name` *Abdulmajeed Alwardi*, `sig_title` *Business Development Executive* (set by the boss).
- **Backend target parameterized — nothing runs locally by default.** New `scripts/nav_env.py`
  centralizes backend resolution: `nav_env.base_url()` reads `NAVAIA_BASE_URL`
  (OS env → `.env` → cloud default `https://fareegi.navaia.sa`); `nav_env.env(key, default)`
  reads secrets from `.env`. Every acting script now calls `nav_env.base_url()` instead of a
  hardcoded `CLOUD_BASE`. The 3 scripts that hit `localhost:8001` (`create_lead_task.py`,
  `monitor_task.py`, `configure_twenty.py`) were repointed to the cloud workforce
  (`131bb52f`, cloud Tariq `6ba49326-…`, `BUSINESS_NF`). Added `NAVAIA_BASE_URL` to `.env` +
  `.env.example`. CRM scripts still hit `crm.navaia.sa` (separate service — untouched).
- **Full reconstructability added.** New `scripts/workforce_snapshot.py` wraps the SDK
  `client.sync` export/import: `export` snapshots the live workforce to
  `workforce/snapshot/workforce_bundle.json` (git-committable); `import [--force]` rebuilds
  it on any backend. Verified export of cloud `131bb52f`: 7 agents, 15 edges, 1 KB, 7
  integrations — **secrets redacted** (`***REDACTED***`, zero leaks), safe to commit.
- **Live private-repo-for-agents investigated → blocked on Navaia.** Goal: agents read our
  private repo (`AkiraKh98/navaia-business-workforce`) dynamically via a fine-grained PAT.
  Verified on this instance: (1) GitHub connect grants only `user:email` scope (no repo
  access — proven by revoke+reconnect showing "Email addresses read-only" only); (2) no
  `github` plugin in the registry — `POST /integrations {plugin_name:"github"}` → 400
  "Plugin 'github' is not registered"; (3) agent `tools` need a registered backing plugin.
  So a PAT can't be self-wired via the SDK. Drafted `workforce/NAVAIA_GITHUB_REQUEST.md`
  asking Navaia to register a GitHub capability (integration plugin OR cloud-runtime MCP
  server) that accepts a read-only fine-grained PAT (Contents: Read).

## 2026-07-05

- Initial draft from user's workflow description.
- Updated verticals from co-founder strategy (5 verticals, 2 tiers). Twenty
  CRM active. Google Places API added. Snov.io scoped to enrichment only.
  E-commerce removed. General hospitals removed — private specialty clinics
  only.

## 2026-07-06

- **Runtime switched** from `claw_code` to `claude_max` (claw CLI missing in
  container).
- **First lead-finding run completed:** 50 leads from Google Places API, 25
  enriched with Snov.io emails. CRM was down — leads in CSV.
- **Added §10** with full execution results and findings.
- **CRM came back up.** Bulk import completed: 35 companies + 35 contacts
  created in Twenty CRM (609 → 645 companies).
- **Cross-language dedup** ran clean (0 dups).
- **Email verification + enrichment pipeline** built and ran.
- **Added §10.10** (Post-Import Pipeline) as the authoritative state
  reference for future sessions.
- **Added §11** (Outreach Strategy) as a placeholder for the next phase —
  pending user's answers to §11.1 questions and inbound-sales research.
- **Outreach strategy built out** (planning only — scripting handed off to
  a separate model). User locked 4 decisions: tone (formal but direct/brief),
  cadence (day 0/+3/+7), channel (email first, WhatsApp later, manual for
  high-priority), targeting (most-responsive contact, not executive-only).
- Ran two research sub-agents → folded findings into §11.3 (inbound-sales
  best practices) and §11.4 (free decision-maker/email lookup playbook).
- Added §11.5 (rules-based 0–100 scoring model) and §11.6 (template
  blueprint).
- **Identity resolved:** عبدالمجيد الوردي / Abdulmajeed Alwardi, نڤايا /
  NAVAIA, https://cal.com/abdulmajeed-alwardi. Drafted first-pass
  per-vertical value props (§11.2).
- Created `OUTREACH_TEMPLATES.md` with the Private Clinics reference
  sequence.
- **User override:** cal.com link + short brief now go in touch 1 (not gated
  behind a reply) — updated §11.6 and the templates accordingly;
  deliverability mitigation (warmed domain + plain-text link) noted for the
  sending model.
- **Touch-1 voice reworked** per user: conversational فصحى (warmth 5→6/10),
  fixed flow (pain subject → company pain → actions-not-how → impact as
  plain fact → regulatory assurance → link), **benefit bank of 3 real
  results** (cost −40–60%, profit +30%, staff productivity) with **2 chosen
  per lead**, MoH + PDPL compliance line stated clearly-not-overstated,
  **no middot bullets**, **4-line signature** (name / Business Development /
  phone / NAVAIA نڤايا). Updated §11.6.
- Positioning rule added: frame as **حلول (solutions), not منصّة (platform)**
  — platform implies work/onboarding for the reader; pair with a "works on
  your behalf, no extra load" clause and a "we start from…" framing.
- **Vertical correction:** earlier templates used a wrong generic set
  (restaurants/retail/professional services). Rebuilt on the **correct 5
  co-founder verticals** (§5.1). `OUTREACH_TEMPLATES.md` now has full
  3-touch sequences for all 5, each with its own pain line, benefit
  pairing, and **vertical-specific compliance** (SAMA for finance, MoH for
  clinics, REGA for real estate, TVTC for training, PDPL throughout).
- **Template copy fixes** per user:
  1. "وأتّصل بكم" → "لأتّصل بكم"
  2. Positive-reply now branches on whether they already booked via
     cal.com (check first, two replies A/B)
  3. "تعمل نيابةً عنكم" (works *instead of* you) → "تعمل إلى جانبكم"
     (works *alongside* you) throughout
  4. The +30% / 40–60% numbers were clinic-only — all other verticals now
     carry placeholders (`{نسبة الأثر}`, `{نسبة التحصيل}`,
     `{نسبة خفض التكاليف}`) for the user to fill.
- **Scripts pruned 65 → 29** — deleted 36 junk (all `test_*`, `debug_*`,
  `inspect_*`, and superseded duplicates); kept the real pipeline.
  Canonical set documented in §10.10.8.
- Gitignored `leads*.csv` (PII) and `scripts/*.json` dumps.
- **Junk data eliminated** ("useful data upfront" rule): deleted 9
  stale/intermediate/duplicate files. **`leads_enriched.csv` (36 leads) is
  now the single source of truth.**
- Handoff clarity for future sessions (any model): added a prominent
  **▶ NEXT STEP** block at the top. Refreshed **§9** — the stale "outreach
  In progress / needs cal.com+tone" row replaced with accurate
  Done/Blocked/Pending rows.
- **Added §0 Current Known-Good Setup + Fixes Applied** at the top of the
  spec — consolidates the actual running config (runtime `claude_max`,
  model `moonshotai/kimi-k2.6`, SDK 0.2.3, JWT→Bearer, DEBUG=true,
  `setup_db.py`) and the fixes that got there.
- Reconstructed §0 from git history + `scripts/fix_runtime.py` /
  `check_runtime.py`. Flags the `ASSESSMENT.md` example drift
  (navaia_code/claude-sonnet-4 is generic, not live).
- Fixed the templates signature to `تطوير الأعمال - Business Development`
  (no brackets, single dash) and regenerated the PDF.
- **Added per-vertical field vocabulary** — each sequence now weaves 2–3
  well-known Arabic field terms to signal domain familiarity, with a
  documented **Field lexicon** line per vertical: Contracting (عروض
  أسعار/RFQ, مناقصات وعطاءات, مواعيد تسليم العطاءات, عقود صيانة وقائية,
  SLA); Finance (محفظة التحصيل, أعمار الديون, الأقساط المتأخّرة, لوائح
  ممارسات التحصيل); Clinics (المراجعين, عدم الحضور/no-show, قائمة
  الانتظار, إشغال الجدول); Real Estate (الوحدات الشاغرة, المعاينة, دفعات
  الإيجار وسنداتها); Training (المتدربين, الالتحاق بالدفعة, المنافسات
  الحكومية, منصة اعتماد/Etimad).

## 2026-07-07

- **Impact numbers confirmed across verticals:** cost −40%, profit +30%.
  Replaced all placeholder tokens and clinic-only range (40–60%) with
  universal figures in both `OUTREACH_TEMPLATES.md` and the spec. Removed
  §9 blocker; updated NEXT STEP (item 1 no longer needs user input).
- **Agent roster restructured to the canonical 7 (boss directive):** the
  workforce is exactly Ahmed (GM), Tariq (SDR), Lina (Marketing), Ghida
  (Creative), Nora (Finance), Rashid (Strategy), Fahad (Account Manager).
  **Never invent agents.** Deleted the two invented standalone agents
  (`zoho_email_outreach_agent.md`, `baian_outreach_agent.md`) — outreach is a
  **capability**, not an agent. Reassigned: **Lina writes** all outreach copy;
  **Tariq sends** (email via **Snov.io campaign → Zoho mailbox**; WhatsApp via
  **Baian, cloud-only**). **Baian = cloud-execution only** (secret lives only in
  cloud; route WhatsApp tasks to cloud, never local). Ahmed's instructions now
  hold the **full capability map** of all 7 agents + the two hard rules. Each
  agent given an **Acceptable Tasks** section + a complete deploy-ready
  `system_prompt`. Reconciled README, `01_workforce_identity`,
  `02_end_to_end_flow`, `07_open_items_and_status`. No keys/secrets touched
  (`.env` and cloud integration config untouched; `10_integration_keys.md` holds
  only shapes). Next: deploy the workforce; thereafter change via PRs.
- **Baian WhatsApp VERIFIED end-to-end.** Two real messages delivered to the owner
  via cloud workforce → Tariq → Baian → Meta template (`meeting_confirmation`, then
  approved custom `navaia_connectivity_test_v1`). Learned: the cloud workforce executes
  tasks even in `draft` (no activation needed); first-contact needs a Meta-APPROVED
  template (`send_template`); new-template approval ≈ minutes; `waiting_blocked` does not
  self-resume. Captured as `playbooks/whatsapp_send_baian.md` + `scripts/baian_send.py` +
  `scripts/check_baian_templates.py`. Baian status corrected Blocked → Active.
- **Repo consolidated into a single executor-ready source of truth.** Renamed
  `workforce_export/` → `workforce/`. Merged + removed duplicate root docs
  (`WORKFLOW_SPEC.md`, `OUTREACH_TEMPLATES.md`) — content lives in `workforce/`. Added a
  root **`AGENTS.md`** entry point (open standard); repointed `START_HERE.md`. Added
  `workforce/playbooks/` (SOP runbooks) and `workforce/tasks/` (self-contained task specs
  — the "container holds only tasks" model). Cleaned `scripts/` (removed sync one-offs,
  bundle/openapi JSON dumps, Baian draft payloads; +2 Baian scripts) → 31 canonical.
  Deleted `logs/` (folded into `deploy_and_sync.md`) and `verification_report.md` (PII,
  superseded by `leads_enriched.csv`). SDK/platform files untouched; no secrets committed.

## 2026-07-08

- **Cloud workforce fully configured:** all 7 agents got their full `system_prompt`
  deployed (`deploy_agents.py`); model cost policy applied (`set_agent_models.py`) —
  kimi ceiling on Lina (customer-facing), qwen + `escalation_model=kimi` + tuned
  `max_turns` on the rest. Baian WhatsApp proven; email limits found + handed to tech
  team (`INTEGRATION_CAPABILITIES_AND_GAPS.md`). Company HTML signature saved to
  `assets/email_signature.html`.
- **Outreach doctrine adopted (HubSpot inbound, adapted to outbound):** buyer-2:1,
  question-close on its own line, <200 words, ≤3-word subjects, ≤5 touches, trigger-event
  openers, free-consult, speed-to-lead. Added to `03_outreach_strategy.md` + Lina's
  instructions (redeployed).
- **All 15 templates rewritten** to the doctrine (`04_outreach_templates.md`) with two new
  opener slots: `{trigger_line}` (from the trigger pass) and `{inbound_context}`
  (reserved/inactive until website inbound exists).
- **Dedup step removed** (boss directive): the **Twenty CRM backend handles duplicates**, so
  the agent no longer checks for dups (it cost tokens for nothing). Add all leads; the CRM
  dumps dups; **count only what was actually added** and **top up until N NEW records exist** —
  the reported number equals the count actually in the CRM. (`dedup_local.py` removed;
  `graphql_dedup`/`crosslang_dedup` kept only as manual reconciliation tools.)
- **Trust-locked review enrichment** (`enrich_reviews.py`, replaces `enrich_triggers.py`):
  reads a lead's OWN Google reviews via the exact `place_id` **and** a matching phone (never a
  name search that could hit a similarly-named business), reasons the specific pain from those
  reviews, and **updates the lead in place** (`pain_line`/`pain_date`, preserving every column
  incl. `created_by`), idempotent, ~$0.0004/lead. **Validated on 5 real leads** → feeds `{trigger_line}`.
- **Handoff notes drafted** (intended for `workforce/HANDOFF.md` — not committed as a standalone
  file; content folded into `AGENTS.md` entry-point section instead). Boss directives captured as
  confirmed: model policy = kimi floor + frontier escalation (pending frontier confirm); dedup +
  email-send = boss mechanism + tech team (no agent-side dedup, no added cost). `START_HERE.md`
  deleted in a later prune (root docs consolidated into `workforce/`).

## 2026-07-10

- **WhatsApp template set pruned + reconciled to the MJ option-B set** (via direct
  Graph API — Baian's create/delete tools were unreliable). Live Meta account 29 → 17.
  Deleted: the `navaia_mj_realestate_t1` **en** duplicate (by `hsm_id`, kept the `ar`), the
  4 superseded vertical originals (`navaia_clinics_t1`, `_v6`, `navaia_contracting_t1`,
  `navaia_realestate_t1`), and 5 stray MJ artifacts (`navaia_mj_clinics_t1_v2`/`_v3`,
  `navaiamjclinicst1`, `mjclinicst001`, `navaia_mj_contracting_t1_20260710_144937`).
  **Kept:** approved MJ set (`navaia_mj_clinics_t1`, `navaia_mj_contracting_t1`,
  `navaia_mj_realestate_t1`), the finance/training `_t1` originals as fallback, and all
  utility/test/survey templates.
- **Two hard Meta template rules discovered (root-causes the finance/training rejections):**
  1. **No trailing/leading variable** — a body may not end (or start) on a `{{n}}`
     (`error_subcode 2388299`). Every approved sibling carries **fixed text after `{{5}}`**
     (realestate: `{{5}}\nشاكراً لكم`) plus an `example.body_text`. Our original bodies ended
     on `{{5}}` with no example → INVALID_FORMAT.
  2. **30-day name lock** — a deleted template's name+language can't be reused for ~30 days
     (`error_subcode 2388023`, "language is being deleted").
- **Finance/training v2 APPROVED** — `navaia_mj_finance_t1_v2` / `navaia_mj_training_t1_v2`
  submitted (fresh `_v2` names to avoid 30-day lock on `_t1`), both polled to APPROVED.
  All 5 option-B MJ Touch-1 templates now live.
- `scripts/manage_wa_templates.py` refactored: removed the stale `run1` mode (which
  attempted an impossible recreate on locked `_t1` names). Added `cleanup` mode — deletes
  everything non-approved in one shot (superseded originals + test junk + old
  `navaia_finance_t1`/`navaia_training_t1`). The `inspect` / `recreate` / `finalize` modes
  remain. DUP_NAME/DUP_HSM_ID constants removed (only one realestate version now).
- Scrubbed a leaked Google Places API key from a FAILED task's `result` in the local DB
  (task `69795c7f`); key rotated in `.env`.

## Setup / SDK Fixes (from git history)

| Commit | Fix |
|--------|-----|
| `b55f0e3` | JWT auth header — SDK sent JWTs as `X-API-Key` → 401. Fixed `http.py` to detect `eyJ` prefix and send JWTs as `Authorization: Bearer`. |
| `b55f0e3` | `DEBUG=false` blocked startup — set `.env.example` to `DEBUG=true` for local dev. |
| `b55f0e3` → `b7b8cae` | DB tables not auto-created — added `scripts/setup_db.py`. |
| `b7b8cae` | Cross-platform DB setup — replaced inline `python -c` with `setup_db.py` + `sys.path` fix. |
| `eb291d2` | Scheduler tables missing — added `import app.scheduler.models` to `setup_db.py`. |
| `b7b8cae`, `c4ec6b4`, `f20f36b` | Version + doc drift — synced `__init__.py` to `0.2.3`; added default timeout; fixed README; pointed `pyproject.toml` + compose URLs to public repo; improved Windows notes. |

## Workforce / Runtime Fixes

| Item | Fix |
|------|-----|
| Runtime `claw_code` → `claude_max` | The `claw` CLI binary is not present in the container. Switched to `claude_max` (uses `claude` wrapper → `navaia -p` → OpenRouter). |
| Agent model = `moonshotai/kimi-k2.6` | Config fact, not a runtime-script fix. `fix_runtime.py` (step 5) and `check_runtime.py` only read/print the model; they don't set it. Model is set at agent creation. |
| Agent malformed JSON for complex tool calls | `moonshotai/kimi-k2.6` via `navaia` CLI produced malformed JSON for bash commands with multi-line scripts. Fallback: direct Python scripts (see `09_canonical_scripts.md`). |
| Container env vars | Only `OPENROUTER_API_KEY` is passed. Other vars must be embedded in task descriptions or added to `docker-compose.yml`. |
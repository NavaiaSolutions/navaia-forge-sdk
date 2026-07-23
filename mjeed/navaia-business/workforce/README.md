# NAVAIA Business — Workforce Export

> **Self-contained snapshot of the "NAVAIA Business" workforce as deployed in the
> hosted container.** This folder is the single source of truth for the workforce
> — every agent, every instruction, every configuration, every operational
> decision — so it can be restored locally without needing the live container.

**Snapshot date:** 2026-07-10
**Workforce name:** NAVAIA Business
**Workforce IDs:**
- Local: `8515d24a-6195-4a73-9cd3-37eb02f08693`
- Cloud: `131bb52f-e5eb-44ad-8134-03dc6908b485`

---

## Folder layout

```
workforce/
├── README.md                          ← you are here (master overview)
├── 00_setup_and_runtime.md            ← known-good config + fixes applied
├── 01_workforce_identity.md           ← IDs, sync, dashboard integration
├── 02_end_to_end_flow.md              ← happy-path orchestration flow
├── 03_outreach_strategy.md            ← §11 strategy, decisions, research
├── 04_outreach_templates.md           ← 5 verticals × 3 touches (Arabic)
├── 05_lead_scoring_model.md           ← §11.5 rules-based 0–100 scoring
├── 06_pipeline_state.md               ← §10.10 post-import pipeline state
├── 07_open_items_and_status.md        ← §9 Done / Blocked / Pending
├── 08_change_log.md                   ← §12 chronological change log
├── 09_canonical_scripts.md            ← §10.10.8 the 29 keeper scripts
├── 10_integration_keys.md             ← integration shapes (no secrets)
├── agents/                            ← exactly 7 agents (never invent more)
│   ├── ahmed_gm_orchestrator.md       ← GM / orchestrator (holds capability map)
│   ├── tariq_sdr_sender.md      ← SDR: finds leads + SENDS (Snov→Zoho email, Baian WhatsApp)
│   ├── lina_marketing.md              ← Marketing: WRITES all outreach copy
│   ├── ghida_creative.md              ← Creative (phased)
│   ├── nora_scorer.md                ← Eligibility & Scoring (phased)
│   ├── rashid_scraper.md             ← Scraper & Importer (phased)
│   └── fahad_account_manager.md       ← Account Manager (phased)
├── playbooks/                         ← executor SOPs (exact steps + commands)
│   ├── lead_pipeline.md               ← fetch → enrich → verify → import (no dedup)
│   ├── email_send_snov.md             ← email outreach (Snov.io → Zoho mailbox)
│   ├── whatsapp_send_baian.md         ← WhatsApp via Baian (PROVEN 2026-07-07)
│   └── deploy_and_sync.md             ← stack deploy, runtime, cloud↔local sync
└── tasks/                             ← reusable self-contained task specs (what the container runs)
    ├── whatsapp_test_send.md
    └── lead_fetch.md
```

> **Entry point:** start with `AGENTS.md` at the repo root — it opens with a project context
> section (timeline, pipeline, CLI guide). Then continue here for the full agent list, folder
> layout, and reading order.

> **Note:** outreach is a *capability*, not an agent. Lina writes, Tariq sends
> (email via Snov.io→Zoho; WhatsApp via Baian, which is **cloud-only**). The former
> standalone "Zoho Email Outreach" and "Baian Outreach" agents were removed.

---

## Workforce at a glance

| Piece | Value |
|-------|-------|
| **Name** | NAVAIA Business |
| **Purpose** | Business-development team (BD intern learning sales + inbound capture) |
| **Runtime mode** | `claude_max` (NOT `claw_code` / `navaia_code`) |
| **Model (all agents)** | `moonshotai/kimi-k2.6` (valid on OpenRouter) |
| **SDK version** | `0.2.3` |
| **Auth** | JWT (`eyJ…`) → `Authorization: Bearer`; long-lived `nf_…` keys → `X-API-Key` |
| **Local dev flag** | `DEBUG=true` in `.env` |
| **DB init** | `scripts/setup_db.py` (run once after first backend start) |
| **Backend** | Local Docker stack, `http://localhost:8001` |
| **Cloud dashboard** | `https://fareegi.navaia.sa` (two-way sync) |
| **CRM** | Twenty CRM — `https://crm.navaia.sa` |
| **OpenRouter key** | `OPENROUTER_API_KEY` in `.env` (already in container env) |

---

## Agents (7 pre-built)

| Name | Role | Status | File |
|------|------|--------|------|
| **Ahmed** | GM (orchestrator) — holds the capability map | Active | `agents/ahmed_gm_orchestrator.md` |
| **Tariq** | SDR: finds leads + **sends** (email via Snov→Zoho, WhatsApp via Baian) | Active | `agents/tariq_sdr_sender.md` |
| **Lina** | Marketing: **writes** all outreach copy | Active (content role) | `agents/lina_marketing.md` |
| **Ghida** | Creative | Phased | `agents/ghida_creative.md` |
| **Nora** | Eligibility & Scoring | Phased | `agents/nora_scorer.md` |
| **Rashid** | Scraper & Importer | Phased | `agents/rashid_scraper.md` |
| **Fahad** | Account Manager | Phased | `agents/fahad_account_manager.md` |

> Note: the workforce has 7 pre-built agents in the backend image (Ahmed + Tariq +
> 5 future). Baian and Zoho are outreach channels wired through integrations, not
> separate agents in the agent table — but they are documented as full agent
> specs because they have their own instructions, tools, and configuration hooks.

---

## How to restore locally

1. **Clone the SDK repo** (or copy this `workforce/` folder into it).
2. **Set up the backend** — see `00_setup_and_runtime.md` for the known-good
   config and the fixes that got there.
3. **Run `scripts/setup_db.py`** once after the first backend start to create
   all tables (including scheduler tables).
4. **Verify runtime** with `scripts/check_runtime.py` — should report
   `claude_max` and `moonshotai/kimi-k2.6` for every agent.
5. **Connect integrations** — see `10_integration_keys.md` for the provider
   list (Snov, Twenty, Zoho, Baian). Twenty is already set up; Snov is
   connected; Baian is blocked.
6. **Sync the workforce** — `local.sync.push(workforce_id, remote=cloud)` to
   pull the cloud workforce down, or `local.sync.pull` to push local up.
   `origin_id` on every entity prevents duplication on round-trips.

---

## What this export does NOT contain

- **Secrets** — API keys, JWT tokens, passwords are NOT in this folder. They
  live in `.env` (which is gitignored). See `10_integration_keys.md` for the
  list of required keys and where to get them.
- **Live runtime state** — task IDs, chat history, scheduler state. Those live
  in the database and the cloud dashboard.
- **The actual outreach sending pipeline** — that's handed to a separate
  scripting model. The templates and scoring model are here; the sending
  automation is not.

---

## Reading order for a new session

If you're a new model picking this up cold, read in this order:

1. `README.md` (this file) — orientation
2. `00_setup_and_runtime.md` — what's actually running and why
3. `01_workforce_identity.md` — IDs, sync, dashboard
4. `agents/ahmed_gm_orchestrator.md` — how the GM works
5. `agents/tariq_sdr_sender.md` — how leads are found
6. `06_pipeline_state.md` — current data + CRM state
7. `07_open_items_and_status.md` — what's done, what's blocked, what's pending
8. `03_outreach_strategy.md` + `04_outreach_templates.md` — outreach plan
9. `05_lead_scoring_model.md` — how leads are prioritized
10. `08_change_log.md` — history of decisions

If you're the **scripting/execution model**, your spec is:
- `05_lead_scoring_model.md` (lead scoring)
- `agents/tariq_sdr_sender.md` → "Outbound Sending" (email via Snov→Zoho, WhatsApp via Baian)
- `agents/lina_marketing.md` (outreach copy) + `04_outreach_templates.md` (content)

If you're a **planning** session, don't write scripts — hand executable work off.
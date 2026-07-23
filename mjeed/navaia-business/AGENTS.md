# AGENTS.md — NAVAIA Business workforce

> **Project Context** — read this section first (under 30s).

### 1. Timeline

- **2026-07-05** — Initial draft. 5 verticals (clinics, contracting, finance, real estate, training), 2 tiers. Twenty CRM active. Google Places + Snov.io scoped.
- **2026-07-06** — First lead run (50 found, 25 enriched). Outreach strategy + all templates built. Impact numbers confirmed (cost −40%, profit +30%). Pipeline scripts pruned 65 → 29.
- **2026-07-07** — Agent roster fixed to canonical 7 (Ahmed, Tariq, Lina, Ghida, Nora, Rashid, Fahad). Baian WhatsApp proven end-to-end. Repo consolidated into `workforce/`.
- **2026-07-08** — Cloud workforce deployed (all 7 agents live). 15 templates rewritten to HubSpot-outbound doctrine. Dedup removed (CRM handles it). Trust-locked review enrichment validated.
- **2026-07-10** — WhatsApp templates pruned 29→17, all 5 vertical MJ Touch-1 approved. Meta API rules (no trailing variable, 30-day name lock) discovered and fixed. Pipeline structural fixes applied: CRM as single source of truth, Mjeed filter, lead status lifecycle, reply flow.

### 2. Pipeline at a Glance

```
User assigns task
  ↓
Ahmed (GM) — parses task, clarifies if ambiguous
  ↓
Rashid (Scraper) — Google Maps / Crawl4AI → import to Twenty CRM (no dedup, NO snov enrichment)
  ↓
Ahmed (GM) — Lina writes copy, Tariq sends
  ↓
Lina (Marketing) — Writes personalized Touch-1 copy via verbatim templates
  ↓
Tariq (Sender) — Halts at HITL gate. Upon approval: sends email via Snov.io, WhatsApp via Baian cloud
  ↓
Tariq — updates CRM leadStatus on send ("Emailed" / "WhatsApped")
  ↓
Replies — CRM updated first ("Replied" / "Meeting Booked"), then Ahmed routes
  ↓
Ahmed — routes follow-ups (positive → cal.com, question → specialist, negative → close)
  ↓
Cadence — day 0 / +3 / +7 touches; CRM leadStatus drives lifecycle
```

> **Hard rules:** (1) Baian WhatsApp is cloud-only. (2) Email goes through Snov.io campaign → Zoho, never Zoho-direct. (3) Only message Mjeed's leads (`createdBy.name = "Mjeed"`). (4) Snov is NEVER used for enrichment, only for email sending.

### 3. CLI Survival Guide (Navaia CLI)

The `navaia` CLI sometimes enters semi-loop patterns with the model. The exact cause isn't fully isolated — the CLI may send nudges asking the model to adjust, but the model doesn't always pick them up correctly. It's an **interaction** problem, not purely a CLI bug or a model bug.

**Observed symptoms (not fully understood):**

- Complex bash (multi-line, pipes, chains) sometimes fails with what looks like a serialization error. Retrying the same call often repeats the failure — the model and CLI fail to converge on a fix.
- Tasks can enter a blocked state where the runtime doesn't self-resume.

**Survival rules (learned from experience, not guaranteed fixes):**

- **Keep every bash call short and single-purpose.** One command, one file, one flag. Avoid multi-line scripts, `&&` chains, or pipes inside a single call.
- If a tool call fails with a parse-looking error, **do not retry the same call.** Re-think: break it into multiple smaller calls, or use a Python script from `scripts/`.
- **Prefer Python scripts in `scripts/`** over inline bash for anything longer than ~3 lines. They sidestep whatever serialization issue occurs.
- If you feel stuck repeating the same failure, **stop and change your approach** — continuing the same path is unlikely to work.
- For long-running external tasks (API calls, imports), use `run_in_background: true` then poll with the Monitor tool — avoids timeouts that can lead to blocked states.

> Entry point for any agent or LLM working in this repo (the [AGENTS.md](https://agents.md/)
> open standard). **The Project Context section above is your first read** — timeline, pipeline,
> and CLI survival guide in under 30 seconds. Then continue to `workforce/README.md` for detailed
> orientation, the agent list, and the full reading order.

## Project overview

**NAVAIA Business** is a business-development workforce of **exactly 7 agents** running on
the **NavaiaForge** platform (this repo is the NavaiaForge SDK; the workforce is the
business overlay in `workforce/`). It finds Riyadh leads across 5 verticals and does
outbound outreach (email + WhatsApp). Runtime: `claude_max` → OpenRouter, model
`moonshotai/kimi-k2.6`.

## The 7 agents (never invent more)

| Agent | Role | Owns |
|-------|------|------|
| **Ahmed** | GM / orchestrator | Routing, tracking; holds the capability map; enforces the hard rules |
| **Rashid** | Scraper | Lead gen (Crawl4AI) + import to Twenty CRM |
| **Lina** | Marketing | **Writes** all outreach copy |
| **Tariq** | Sender | Hits HITL gate, sends (email via Snov + WA via Baian) |
| **Ghida** | Creative | Visual identity / design (phased) |
| **Nora** | Finance | Pricing, billing, reporting (phased) |
| **Fahad** | Account Manager | Post-sale success (phased) |

Full per-agent instructions: **`workforce/agents/`**. Outreach is a **capability**, not an
agent — there is no standalone email or WhatsApp agent.

## Two hard rules

1. **Baian (WhatsApp) is CLOUD-ONLY.** Its secret lives only in the cloud runtime. Route
   any WhatsApp/Baian task to the cloud; never run it locally.
2. **Email sends through Snov.io** (campaign → connected Zoho mailbox), **never Zoho
   directly.**

## How to run things (executor SOPs)

Each is a step-by-step playbook with exact commands:
- **`workforce/playbooks/lead_pipeline.md`** — fetch → clean → dedup → enrich → verify → import.
- **`workforce/playbooks/email_send_snov.md`** — email outreach (Snov → Zoho).
- **`workforce/playbooks/whatsapp_send_baian.md`** — WhatsApp via Baian (PROVEN).
- **`workforce/playbooks/deploy_and_sync.md`** — stack deploy, runtime, cloud↔local sync.

## How to dispatch a task to the workforce

The container holds thin agent shells; **behaviour comes from self-contained task specs in
`workforce/tasks/`**. Dispatch via the canonical scripts:
```bash
.venv/Scripts/python.exe scripts/baian_send.py --template <approved_template>   # WhatsApp
.venv/Scripts/python.exe scripts/create_lead_task.py                            # lead finding
.venv/Scripts/python.exe scripts/check_cloud_integrations.py                    # read-only: what's connected
```
Cloud workforce id `131bb52f-e5eb-44ad-8134-03dc6908b485`; Tariq (sender)
`6ba49326-4ec0-4b3b-8651-9526ec96894e`.

## Setup

```bash
python -m venv .venv && .venv/Scripts/pip install -e packages/python
docker compose -f docker-compose.dist.yml up -d
.venv/Scripts/python.exe scripts/setup_db.py
.venv/Scripts/python.exe scripts/check_runtime.py   # expect claude_max + moonshotai/kimi-k2.6
```

## Secrets & data

- Secrets live in **`.env`** (gitignored) — `BUSINESS_NF`, `TWENTY_TOKEN`, `SNOV_*`,
  `ZOHO_*`, `PLACES_API`, `MY_PHONE`, `OPENROUTER_API_KEY`. **Never commit them.** Baian's
  token is **not** here — it's cloud-only. Shapes documented in `workforce/10_integration_keys.md`.
- `leads_enriched.csv` (PII) is the single lead dataset — **gitignored**, never commit.

## Repo map

- `workforce/` — business source of truth (agents, `00–10` knowledge docs, `playbooks/`, `tasks/`).
- `scripts/` — canonical Python executors (lead pipeline, CRM utils, task ops, Baian send).
- `packages/`, `examples/`, `docs/`, `ASSESSMENT.md` — the NavaiaForge SDK/platform (do not modify for business changes).

## Change discipline

`workforce/` is the source of truth. Deploy the workforce once, then make changes via
**PRs** against this repo — not ad-hoc edits to the live cloud entity.

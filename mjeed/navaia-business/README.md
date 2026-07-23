# NAVAIA Business — Workforce (private)

Private business overlay for the **NAVAIA Business** workforce (7-agent BD team) running
on the NavaiaForge platform. This repo holds the business ops — agent instructions,
knowledge, playbooks, task specs, and executor scripts. The NavaiaForge **SDK** is a
separate public repo (`NavaiaSolutions/navaia-forge-sdk`); this repo depends on it but
does not contain it.

## Start here

- **`AGENTS.md`** — the entry point for any agent/LLM. Read it first.
- **`workforce/`** — source of truth: `agents/`, `playbooks/` (executor SOPs),
  `tasks/` (self-contained task specs), and the `00–10` knowledge docs.
- **`scripts/`** — canonical Python executors (lead pipeline, CRM utils, Baian send).

## Setup

```bash
python -m venv .venv
.venv/Scripts/pip install navaia-forge          # the published SDK
cp .env.example .env                             # then fill in your secrets
```

Run the local backend from the SDK (`docker compose -f docker-compose.dist.yml up -d`)
if needed; most ops talk to the cloud workforce + CRM/Snov directly.

## Secrets & data

- Secrets live in **`.env`** (gitignored) — never commit. Baian's token is cloud-only.
- `leads_enriched.csv` (PII) is **gitignored** — kept local, never committed.

# HANDOFF — current state for the next machine (2026-07-12)

> Canon for orientation is **`AGENTS.md`** + the numbered `workforce/` docs +
> `playbooks/`. This file is only the **machine-move state**: what changed this
> session and where to pick up. (The old 2026-07-08 handoff was retired as
> stale — its rules already live in `AGENTS.md` / the numbered docs.)

## 2026-07-13 — since this handoff
- **Cloud-only by default.** `scripts/nav_env.py` resolves the backend from `NAVAIA_BASE_URL`
  (default cloud `fareegi.navaia.sa`); every acting script uses it, and the 3 `localhost:8001`
  scripts (`create_lead_task.py`, `monitor_task.py`, `configure_twenty.py`) were **repointed to
  cloud** (`131bb52f`, cloud Tariq, `BUSINESS_NF`). No local Docker needed to operate.
- **Reconstruct-anywhere:** `scripts/workforce_snapshot.py export/import` +
  `workforce/snapshot/workforce_bundle.json` (secrets redacted) rebuild the workforce on any backend.
- **Live private-repo-for-agents = blocked on Navaia.** This Fareegi instance can't grant repo
  access (GitHub connect is `user:email` only; no `github` plugin; can't self-wire a PAT via the
  SDK). Request drafted: `workforce/NAVAIA_GITHUB_REQUEST.md` (read-only fine-grained PAT).

## Machine / repos
- Work moved off the original `aabbo` machine → this session's machine → next machine.
- **Private repo `AkiraKh98/navaia-business-workforce` = single source of truth.**
- Security fix: strategy had leaked to the **public** SDK fork; synced to private
  and **`akira/dev` deleted** from the public fork (now 404s). Public fork keeps
  only `main` + `fix/local-setup-docs` (PR #20). **Never commit strategy to the fork.**
- No secrets/PII ever committed (full-history scan clean).

## Workforces
- **Cloud `131bb52f`** (fareegi, key `BUSINESS_NF`) = **operational home** per boss
  ("keep it cloud-tied — Baian + imminent full deploy").
- Local `9d409beb` (localhost:8001) = exploratory copy pulled via `client.sync.pull`.
- **All 7 agents set to `moonshotai/kimi-k2.6`** (cloud + local).

## The pipeline to run
`Ahmed(GM) → Tariq(lead-gen→CRM) → Lina(copy) → [HUMAN REVIEW] → Tariq(send)`.
Routing: **phone-only → WhatsApp (Baian/cloud); has-email → email (Snov→Zoho)**.
Verticals: Real Estate + Contracting/Facilities, 10 each.

## CRM state now
**6 leads added this session** via `scripts/leadgen_overpass.py`
(`leadSource=OpenStreetMap`): **5 Real Estate + 1 Contracting & Facilities**,
all phone + no email → **all WhatsApp candidates**.

## Blockers
- **Google Places 403 = billing** (no active billing account on the GCP project;
  key `…6lAc_s` is correct). Enable billing → `scripts/leadgen_2vertical.py` for full yield.
- **Overpass/OSM** flaky (504) but works on the mail.ru mirror; thin phone coverage.
- **Agent plan-gate:** `claude_max` forces `[WAITING:PLAN]` and loops; no config
  toggle exists. Reliable execution = scripts, not agent tool-calls.
- **`aabbo` scripts** — `create_lead_task.py` was **repointed to cloud + fixed** (2026-07-13,
  uses `nav_env`); `import_all_leads.py` still stale — prefer `scripts/leadgen_2vertical.py` /
  `leadgen_overpass.py` for lead-gen runs.

## New scripts
`scripts/leadgen_2vertical.py` (Places→CRM) · `scripts/leadgen_overpass.py` (OSM→CRM, no billing).

## Pick-up (new machine)
Clone private repo → drop `.env` + `_local_api_key` → enable Places billing →
`leadgen_2vertical.py` → enrich → Lina copy → **review** → send (cloud).

---

## ⚠️ Two items inherited from the retired 2026-07-08 handoff — VERIFY (may be stale/resolved)
1. **Model policy:** boss wanted kimi as the **FLOOR** + escalate to a **FRONTIER**
   model (recommended `claude-opus-4.8`), frontier slug **pending confirmation**.
   Floor=kimi is now set; **frontier `escalation_model` not applied.** Confirm if still wanted.
2. **Branded email send was BROKEN** (`zoho_mail.send` plain-text only; Snov has no
   send) — confirm whether the tech team resolved this before shipping email outreach.

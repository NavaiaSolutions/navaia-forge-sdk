# 00 — Setup & Runtime (Known-Good Config + Fixes Applied)

> **Authoritative record of how the NAVAIA Business workforce is *actually*
> configured and working in the hosted container**, plus the fixes that got
> it there. Reconstructed from git history + the runtime scripts in `scripts/`.

---

## Known-Good Current Config

| Piece | Current value |
|-------|---------------|
| Backend | Local Docker stack, `http://localhost:8001` (all execution + storage here) |
| Workforce name | "NAVAIA Business" |
| Workforce ID (local) | `8515d24a-6195-4a73-9cd3-37eb02f08693` |
| Workforce ID (cloud) | `131bb52f-e5eb-44ad-8134-03dc6908b485` |
| **Runtime mode** | **`claude_max`** (NOT `claw_code` / `navaia_code`) |
| **Model (all agents)** | **`moonshotai/kimi-k2.6`** (valid on OpenRouter) |
| Agents | 7 pre-built (Ahmed GM + Tariq SDR + 5 future) |
| SDK version | `0.2.3` (PyPI, `__init__.py`/`pyproject.toml` synced) |
| Auth | JWT (`eyJ…`) → `Authorization: Bearer`; long-lived `nf_…` keys → `X-API-Key` |
| Local dev flag | `DEBUG=true` in `.env` (required locally) |
| DB init | `scripts/setup_db.py` (run once after first backend start) |

---

## Fixes Applied (what was broken → what fixed it)

### Setup / SDK (from git history)

1. **JWT auth header** — SDK sent JWT tokens as `X-API-Key`, so the backend
   couldn't resolve the user → 401 "User not found" and 500 on API-key creation.
   Fixed `http.py` to detect the `eyJ` prefix and send JWTs as `Authorization:
   Bearer`; `nf_…` keys still go as `X-API-Key`. (SDK `0.2.3`, `b55f0e3` / `4e4a7dd`)

2. **`DEBUG=false` blocked startup** — backend refused to boot with localhost-only
   `ALLOWED_ORIGINS`. `.env.example` set to `DEBUG=true` for local dev. (`b55f0e3`)

3. **DB tables not auto-created** — the backend image does not auto-migrate, so
   a fresh install had no tables. Added `scripts/setup_db.py` that imports every
   SQLAlchemy model and runs `create_all`. (`b55f0e3` → `b7b8cae`)

4. **Cross-platform DB setup** — replaced the inline `python -c` one-liner (broke
   on Windows PowerShell quoting) with `setup_db.py`, plus a `sys.path` fix so it
   runs without `-e PYTHONPATH=/app`. (`b7b8cae`)

5. **Scheduler tables missing** — added `import app.scheduler.models` to
   `setup_db.py` so scheduler/pipeline tables are created. (`eb291d2`)

6. **Version + doc drift** — synced `__init__.py` to `0.2.3`; added a default
   timeout to `HttpConfig` (standalone WS example); fixed README (`send_message`
   takes no `agent_id`; `integrations.create` needs `workforce_id` + `config_json`);
   pointed `pyproject.toml` + compose download URLs to the public
   `NavaiaSolutions/navaia-forge-sdk`; improved Windows notes (`curl.exe`, setup
   script download). (`b7b8cae`, `c4ec6b4`, `f20f36b`)

### Workforce / runtime (from `scripts/fix_runtime.py`)

7. **Runtime `claw_code` → `claude_max`** — the `claw` CLI binary is not present in
   the container, so tasks couldn't execute. Switched the "NAVAIA Business"
   workforce to `claude_max` (the `claude` wrapper calls `navaia -p`, routing
   through OpenRouter). Verify with `scripts/check_runtime.py`.

8. **Agent model = `moonshotai/kimi-k2.6`** — this is a *config fact*, not a fix
   by the runtime script: `fix_runtime.py` (step 5) and `check_runtime.py` only
   **read and print** each agent's `model_name` to confirm it; they do not set
   it. The model is configured at agent creation and treated as valid on
   OpenRouter.

---

## Drift to Be Aware Of

`ASSESSMENT.md` (the candidate brief) still shows the *generic example* config —
`runtime_mode="navaia_code"` and `anthropic/claude-sonnet-4`. **That is a
template, not the running workforce.** The live workforce uses `claude_max` +
`moonshotai/kimi-k2.6` as in the table above. Don't copy the assessment example
values into the real workforce.

---

## Environment Variables

| Var | Required | Source | Notes |
|-----|----------|--------|-------|
| `OPENROUTER_API_KEY` | Yes | `.env` | Already in container env |
| `SECRET_KEY` | Yes | `.env` | Generate with `openssl rand -hex 32` |
| `ALLOWED_ORIGINS` | Yes | `.env` | Must include `http://localhost:8001` for local |
| `BUSINESS_NF` | Yes | `.env` | Workforce API key (`nf_…`) |
| `DEBUG` | Yes (local) | `.env` | Must be `true` for local dev |
| `NAVAIA_BACKEND_VERSION` | No | `.env` | Default: `latest` |
| `API_PORT` | No | `.env` | Default: `8001` |
| `POSTGRES_USER` / `_PASSWORD` / `_DB` | No | `.env` | DB config (defaults shown) |
| `WEAVIATE_API_KEY` | No | `.env` | Leave empty for anonymous access |
| `GITHUB_TOKEN_ENC_KEY` | Yes | `.env` | Fernet key for token encryption |
| `MY_PHONE` | No | `.env` | User's phone (for signature) |
| `TWENTY_TOKEN` | Yes (CRM) | `.env` | Twenty CRM JWT |
| `TWENTY_SESSION` | No | `.env` | Twenty session cookie |
| `ZOHO_MAIL` | Yes (email) | `.env` | Zoho account email |
| `ZOHO_PASS` | Yes (email) | `.env` | Zoho account password |
| `SNOV_USER_ID` | Yes (enrich) | `.env` | Snov.io user ID |
| `SNOV_USER_SECRET` | Yes (enrich) | `.env` | Snov.io user secret |
| `PLACES_API` | Yes (leads) | `.env` | Google Places API key |

> **Container env var caveat:** only `OPENROUTER_API_KEY` is passed to the
> container by default. Other `.env` vars (`PLACES_API`, `TWENTY_TOKEN`,
> `SNOV_*`, `ZOHO_*`) are NOT available inside the container. They must be
> embedded in task descriptions or added to `docker-compose.yml`.

---

## Docker Stack

- **`docker-compose.dist.yml`** — the distributed compose file
- Base URL: `http://localhost:8001`
- Services: API, Postgres, Weaviate, scheduler, etc. (per compose file)

---

## Database Init (one-time)

```bash
cd /path/to/repo
python scripts/setup_db.py
```

This imports every SQLAlchemy model (including `app.scheduler.models`) and
runs `create_all` to create all tables. Run once after the first backend
start on a fresh install.

---

## Runtime Verification

```bash
python scripts/check_runtime.py
```

Expected output:
- Workforce: "NAVAIA Business" (`8515d24a-…` local / `131bb52f-…` cloud)
- Runtime mode: `claude_max`
- Model (all 7 agents): `moonshotai/kimi-k2.6`

If any agent shows the wrong model or runtime mode, run
`python scripts/fix_runtime.py` to correct it.
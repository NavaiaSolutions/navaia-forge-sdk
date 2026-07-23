# Playbook — Deploy & Sync (container topology, runtime, cloud↔local sync)

> Absorbs the 2026-07-07 container-deployment log and the sync-debugging one-off scripts.
> SOP for standing up the stack and keeping repo/local/cloud coherent.

## Topology

```
Fareegi Cloud (https://fareegi.navaia.sa)     Local Docker stack (http://localhost:8001)
  - dashboard / UI, outputs, chats      <-->    - API (FastAPI), scheduler, Postgres,
  - scheduler surface, integrations cfg  sync     Weaviate, OpenRouter routing, agent runtime
  - Baian token lives HERE (cloud-only)          - reads secrets from .env (gitignored)
```

- **Local container = where work runs. Cloud = monitoring surface.** If they disagree,
  local wins for execution — **except Baian**, which is cloud-only (see
  `whatsapp_send_baian.md`).
- Same workforce name on both, different IDs: local `8515d24a-6195-4a73-9cd3-37eb02f08693`,
  cloud `131bb52f-e5eb-44ad-8134-03dc6908b485`. Sync round-trips on `origin_id`.
- **Container env caveat:** only `OPENROUTER_API_KEY` is passed to the container by
  default. Other `.env` vars (`PLACES_API`, `TWENTY_TOKEN`, `SNOV_*`, `ZOHO_*`) must be
  embedded in task descriptions or added to `docker-compose.yml`.

## Deploy from a fresh install

```bash
git clone <repo> && cd navaia-forge-sdk
python -m venv .venv
.venv/Scripts/pip install -e packages/python
docker compose -f docker-compose.dist.yml up -d
curl http://localhost:8001/health              # -> {"status":"healthy",...}
.venv/Scripts/python.exe scripts/setup_db.py   # one-time DB init (incl. scheduler tables)
.venv/Scripts/python.exe scripts/check_runtime.py   # expect claude_max + moonshotai/kimi-k2.6
```
If `check_runtime.py` shows anything but `claude_max` / `moonshotai/kimi-k2.6`, run
`scripts/fix_runtime.py`.

## Runtime_mode drift (the 2026-07-07 gotcha)

- `runtime_mode` decides *how* a task runs once an agent calls a tool. The container has
  only the `claude` wrapper (→ `navaia -p` → OpenRouter). So:
  - `claude_max` → routes via OpenRouter → **works**.
  - `navaia_code` / `claw_code` → invoke bare binaries not in the container → **fail**, silently.
- Detect: `scripts/check_runtime.py` (local) or GET the cloud workforce and read
  `runtime_mode`. Fix one field without clobbering the rest with a surgical PUT:
  ```bash
  # via SDK: cloud.workforces.update(cloud_wf, runtime_mode="claude_max")
  ```

## Sync rules

- **A bundle sync is a schema merge, not a secret push.** Cloud exports ship a
  `redacted_fields` list; the import side honours it and does NOT overwrite local secrets.
  Do not "force-sync" tokens. Populate secrets via `PUT /integrations/{id}` instead, and
  re-authenticate after any sync touching a non-empty `config_json`.
- **Before syncing:** diff the two sides first (list workforces/agents/integrations/edges
  on each and compare) so you decide push vs pull vs surgical PUT before any write.
- **To change one field** on a workforce/agent, use the targeted `PUT` — not a full
  bundle push.

## Deploy-then-PR discipline

The `workforce/` folder (agent instructions + these playbooks + task specs) is the
**source of truth**. Deploy the workforce once, then make changes via **PRs** against this
repo — not ad-hoc edits to the live entity.

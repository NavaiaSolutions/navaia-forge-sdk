# Local Setup — Failure Modes & Fixes

> **What this is.** A triage reference for every way a fresh `git clone` → running
> local workforce can fail, with the root cause and the exact fix for each.
> Written for Linux, macOS, Windows/PowerShell, and Windows/Git Bash.
>
> **Legend.**
> - ✅ **Shipped** — already handled by the current code/config; documented here
>   so support can recognize it if an older install hits it.
> - ⚠️ **This change** — a documentation gap addressed by the PR that adds this
>   file (`SETUP.md`, `scripts/setup_db.py` docstring).
>
> Each section is **Symptom → Root cause → Fix**.

---

## TL;DR — the checklist a clean install actually needs

```bash
# 1. Clone + configure
git clone https://github.com/NavaiaSolutions/navaia-forge-sdk.git
cd navaia-forge-sdk
cp .env.example .env
#   → set SECRET_KEY, POSTGRES_PASSWORD, and ONE runtime key (see §9)
#   → keep DEBUG=true for local dev (see §2)

# 2. Start the stack
docker compose -f docker-compose.dist.yml up -d

# 3. Create the database schema (the image does NOT auto-migrate — see §3)
docker cp scripts/setup_db.py navaia-forge-api:/tmp/
docker exec navaia-forge-api python /tmp/setup_db.py     # Git Bash: see §5

# 4. Verify
curl http://localhost:8001/health        # Windows PowerShell: curl.exe
```

---

## §1 — JWT tokens sent with the wrong auth header ✅ Shipped

**Symptom.** After `client.auth.register(...)` / `login(...)`, the next call —
creating a long-lived API key — fails with `401 User not found` (sometimes
surfaced as `500`).

**Root cause.** The transport attached every credential as `X-API-Key`. But
`register`/`login` return a **JWT**, which the backend only accepts as
`Authorization: Bearer`. The user was never resolved, so the authenticated call
looked unauthenticated.

**Fix.** Branch on token shape in `HttpClient._build_headers`
(`packages/python/navaia_forge/http.py`). JWTs begin with `eyJ`; long-lived keys
begin with `nf_`.

```python
if key.startswith("eyJ"):
    headers["Authorization"] = f"Bearer {key}"
else:
    headers["X-API-Key"] = key
```

---

## §2 — `DEBUG=false` blocked first boot ✅ Shipped

**Symptom.** The container starts but never becomes healthy; logs reject the
localhost-only `ALLOWED_ORIGINS`.

**Root cause.** `.env.example` shipped `DEBUG=false`. Production mode rejects a
localhost CORS list as insecure — but localhost is exactly what a local install
has.

**Fix.** `.env.example` ships `DEBUG=true` with a comment explaining it is the
local-dev default.

---

## §3 — Database schema never created on a fresh install ✅ Shipped

**Symptom.** `/health` returns `200`, but the first real SDK call returns `500`
with Postgres `relation "..." does not exist`.

**Root cause.** The distributed backend image does not run migrations on
startup; a new Postgres volume has zero tables.

**Fix.** Run `scripts/setup_db.py` once after `up`, as a mandatory step in
`SETUP.md` Step 1:

```bash
docker cp scripts/setup_db.py navaia-forge-api:/tmp/
docker exec navaia-forge-api python /tmp/setup_db.py     # → "Database ready"
```

---

## §4 — `setup_db.py` docstring still shows a `PYTHONPATH` flag ⚠️ This change

**Symptom.** Following the script's own docstring, a reader keeps the
`-e PYTHONPATH=/app` flag that the code no longer needs — and may assume it is
required elsewhere.

**Root cause.** The script self-locates `/app` on `sys.path`, so the flag is
obsolete, but the module docstring was never updated after that change.

```python
app_dir = Path("/app")
if app_dir.is_dir() and str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))
```

**Fix.** Update the docstring to the flag-free command (and mention the Git Bash
caveat from §5).

---

## §5 — Git Bash silently mangles the `/tmp/` path ⚠️ This change

**Symptom.** On Windows **Git Bash / MSYS2**, the documented command:

```bash
docker exec navaia-forge-api python /tmp/setup_db.py
```

fails with:

```
python: can't open file '/app/C:/Users/<you>/AppData/Local/Temp/setup_db.py':
[Errno 2] No such file or directory
```

**Root cause.** MSYS "POSIX path conversion" rewrites any argument that looks
like a Unix absolute path (`/tmp/...`) into a Windows path **before** it reaches
`docker.exe`. The container never receives `/tmp/setup_db.py`. This is invisible
— the command looks correct and fails naming a path the user never typed. It is
distinct from the PowerShell `curl` note: PowerShell is fine, Git Bash is not,
and Git Bash is a very common Windows shell for anyone who followed
`git clone`.

**Fix.** Document all shells in `SETUP.md` Step 1:

```bash
# Git Bash / MSYS2 — disable path conversion for this one command:
MSYS_NO_PATHCONV=1 docker exec navaia-forge-api python /tmp/setup_db.py
# or double the leading slash, which MSYS leaves untouched:
docker exec navaia-forge-api python //tmp/setup_db.py
```

```powershell
# PowerShell / CMD — works as written:
docker exec navaia-forge-api python /tmp/setup_db.py
```

---

## §6 — SDK version drift ✅ Shipped

`__init__.py` and `pyproject.toml` are pinned to the published release (`0.2.3`).
Follow-up worth filing: single-source the version
(`importlib.metadata.version("navaia-forge")`) so it cannot recur.

---

## §7 — README snippets vs. the SDK API ✅ Shipped

`conversations` now takes `agent_id` on `create(...)`, not `send_message(...)`,
and `integrations.create(...)` uses `workforce_id` + `config_json`. Follow-up:
a CI doctest that runs README/SETUP Python blocks so docs can't drift again.

---

## §8 — `pyproject.toml` project URLs ✅ Shipped

`[project.urls]` points at the canonical `NavaiaSolutions/navaia-forge-sdk`.

---

## §9 — Docs contradict themselves on runtime + model naming ⚠️ This change

The highest-impact documentation gap, because it fails *after* everything else
is right — during the first task run — with an error that doesn't point back at
the docs.

**Symptom.** A task created per the docs fails with *"can't reach the language
model"* / invalid-model, though the backend is healthy and authenticated.

**Root cause.** The docs describe two different runtimes as if they were one:

| Source | `runtime_mode` | `model_provider` | `model_name` |
|---|---|---|---|
| `ASSESSMENT.md` (Phase 3) | `navaia_code` | `openrouter` | `anthropic/claude-sonnet-4` (full ID) |
| `SETUP.md` (Step 5) | *(omitted)* | `anthropic` | `sonnet` |
| `examples/python/*.py` (all) | `claude_max` | `anthropic` | `sonnet` |

Two problems at once:

1. **Prerequisites vs. examples.** `ASSESSMENT.md` requires an **OpenRouter** key
   (`navaia_code`), but `SETUP.md` and every example default to **`claude_max`**
   (Claude Code CLI). A user who set up OpenRouter, then copied an example, is
   running a runtime they never configured.
2. **Naming convention differs per runtime.** `navaia_code`/OpenRouter needs a
   **full** ID (`anthropic/claude-sonnet-4`); a bare `sonnet` is invalid there.
   `claude_max`/Claude Code accepts the short alias `sonnet`. The docs mix them.

**Fix.** Make every getting-started snippet internally consistent and state the
per-runtime rule once:

- `SETUP.md` Step 2 gains a **"Match `model_name` to your runtime"** table.
- `SETUP.md` Step 5 sets `runtime_mode="claude_max"` explicitly (so its
  `model_name="sonnet"` is valid) and comments the `navaia_code` alternative.
- The examples are labeled as targeting `claude_max`.

| Runtime | Configure | `model_provider` | `model_name` |
|---|---|---|---|
| `navaia_code` | `OPENROUTER_API_KEY` in `.env` | `openrouter` | `anthropic/claude-sonnet-4` |
| `claude_max` | `claude login` on host | `anthropic` | `sonnet` |

---

## How this was verified

- Clean-stack walkthrough on empty volumes reproduces §1–§4 pre-fix and passes
  post-fix.
- §5 reproduced live: the documented `docker exec ... /tmp/setup_db.py` under Git
  Bash fails with the mangled `'/app/C:/Users/.../setup_db.py'` path; both
  `MSYS_NO_PATHCONV=1` and `//tmp/` succeed; PowerShell succeeds unchanged.
- §9 confirmed by cross-reading `ASSESSMENT.md` Phase 3 against `SETUP.md` Step 5
  and all `examples/python/*.py`: runtime and model-name conventions disagree.

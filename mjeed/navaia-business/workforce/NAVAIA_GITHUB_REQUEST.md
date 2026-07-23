# Request to Navaia — give our agents live read access to our private GitHub repo (via a fine-grained PAT)

**What we need:** let our workforce's agents read our **private** GitHub repo *live* (dynamically, at task time) so our scripts + SOPs are always current — no snapshot pushing. We want to authenticate this with a **fine-grained Personal Access Token** scoped **read-only to one repo**, which we'll send securely. We can't wire this ourselves — it needs a server-side capability we don't control (see evidence below).

**Workforce id:** `131bb52f-e5eb-44ad-8134-03dc6908b485`
**Repo:** `AkiraKh98/navaia-business-workforce` (private), default branch `main`

---

## Why we can't self-serve (what we already tested)

1. **No GitHub plugin in the registry.** `GET /api/v1/plugins` returns 9 plugins (telegram, trello, apollo, hunter, snov, twenty, zoho, crm, baian) — no `github`. Attempting to install one is rejected server-side:

   ```
   POST /api/v1/integrations  {plugin_name:"github", config_json:{token:"<pat>"}}
     → 400 {"detail":"Plugin 'github' is not registered"}
   ```

2. **The GitHub connect flow is identity-only.** `GET /api/v1/auth/github` → `github.com/login/oauth/authorize?client_id=Ov23li2YZV7384vhuzdw&scope=user:email`. After revoking the app on GitHub and reconnecting, the fresh authorize screen requests **only "Email addresses (read-only)"** — **no repository / Contents scope**. So a knowledge-base "connect GitHub repo" can never see a private repo; it returns "Repo not found."

3. **Agent `tools` need a backing plugin.** The agent `tools` list accepts arbitrary entries, but the runtime only executes tools backed by a registered plugin — so we can't inject a working GitHub tool from the SDK.

Net: reading our private repo requires a **server-side capability you register**, plus our PAT. Everything up to that point we've done.

---

## What we're asking you to add (either option works for us)

**Option A — a `github` integration plugin** (mirrors your existing plugin pattern, e.g. `twenty`/`baian`):
- `config_schema`: `{ token (secret, fine-grained PAT), repo (default "AkiraKh98/navaia-business-workforce"), ref (default "main") }`
- Tools exposed to the agent: at minimum `read_file(path)` and `list_dir(path)` (optionally `search_code`) against the configured repo at the current ref — **read-only**.

**Option B — a GitHub MCP server in our workforce's cloud runtime** (`.navaia/config.json` that the `navaia` CLI runtime loads), wrapped as `mcp__github__*`, authenticated by the same PAT. Same read-only outcome; this is the more "live" path.

Either way the token is a **fine-grained PAT** we generate with **Repository access: only `navaia-business-workforce`**, **Permissions → Contents: Read-only** (Metadata: Read is implied). Least privilege — no write, no other repos. We'll deliver the PAT over a secure channel, not in this doc.

---

## Why this matters to us

Our agents' operating scripts and SOPs live in git (config-as-code, per the deploy-ready mandate). We want the agents to use the **current** repo state on every task without us re-uploading snapshots into a knowledge base. A read-only fine-grained PAT behind a GitHub tool/MCP server on the always-on cloud runtime is the least-privilege way to make that dynamic. If neither option is on your near-term roadmap, tell us and we'll fall back to a knowledge-base push-sync in the meantime.

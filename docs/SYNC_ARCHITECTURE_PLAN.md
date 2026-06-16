# NavaiaForge Two-Way Sync — Architecture Plan

**Date**: 2026-06-12
**Status**: v2 — post-audit (code-verified against backend + SDK; all critical findings fixed)
**Author**: Rakan + Claude
**Branch**: `feat/personal-assistant-workforce`

> **v2 changes**: replaced export-time `bundle_ref` with a propagating per-entity
> `origin_id` (fixes ref instability across exports AND round-trip duplication),
> content-only canonical hash (fixes idempotency), completed the bundle schema
> against real models (`escalation_model`, `condition_expr`, `max_runs`,
> `task_mode`), KB-reference remapping inside agents, deny-by-default secret
> redaction, defined conflict timestamps, marketplace fork KB cloning,
> body-size/entity-count/rate limits, SDK-orchestrated topology made explicit.

---

## 1. Problem Statement

NavaiaForge users run the backend locally via Docker for compute (LLM calls
stay on their machine). They need to **push** their workforces to the cloud
(Fareegi) so they can:

- Visualize workforces in the Fareegi UI
- Publish to the marketplace for others to discover and buy
- Collaborate with team members

They also need to **pull** workforces from the cloud:

- Download marketplace purchases to run locally
- Clone public/shared workforces to their local instance

Today, local and cloud are completely isolated — no data flows between them.

---

## 2. Design Principles

1. **Docker Hub model** — users already understand `push` and `pull`.
   Build locally, push to cloud, others pull. No real-time collaboration
   needed.

2. **Local-first** — local instance is the source of truth for compute.
   Cloud is the source of truth for marketplace and discovery. Sync is
   explicit, not automatic.

3. **Start simple, evolve incrementally** — snapshot sync first, incremental
   change feed later (only if needed).

4. **No backend rewrite** — add endpoints to existing codebase. Both local
   and cloud run the same code.

5. **Secrets never leave the instance** — integration credentials are
   stripped on export (deny-by-default). Users re-authenticate on import.

6. **Atomic imports** — import is all-or-nothing. If any entity fails
   validation, the entire transaction rolls back. No partial state.

7. **SDK-orchestrated, client-side sync** — the SDK client makes both HTTP
   calls (export from A, import to B). **Backends never talk to each
   other.** No server-to-server credentials, works behind NAT/firewalls,
   and the user's API keys for each instance stay on the user's machine.

8. **Identity travels with the data** — every synced entity carries a
   permanent `origin_id` that propagates through every push/pull hop, so
   re-syncing in *either* direction updates rather than duplicates.

---

## 3. What Gets Synced

### Always synced (configuration/topology)

| Entity | Description | Typical Size |
|--------|-------------|-------------|
| Workforce | Name, description, runtime mode, config | ~1 KB |
| Agents | Name, role, instructions, model config, escalation model, position | ~2-5 KB each |
| Edges | Source/target agent, approval mode, label, condition_expr, max_runs, task_mode | ~0.3 KB each |
| Knowledge Bases | Metadata + text content (name, description, repos, texts) | ~0.5-5 KB each |
| Integrations | Plugin name, display name, config (secrets stripped, deny-by-default) | ~0.3 KB each |

### Optionally synced (runtime data)

| Entity | Description | When to include |
|--------|-------------|-----------------|
| Tasks + TaskLogs | Execution history | Push to cloud for dashboard visualization |
| Conversations + Messages | Chat history | Push to cloud for review/analytics |

### Never synced

| Entity | Reason |
|--------|--------|
| Knowledge base documents (binary files) | Too large for JSON bundle — separate endpoint later |
| Integration secrets (API keys, tokens, webhook URLs) | Security — must re-authenticate on import |
| GitHub OAuth tokens (knowledge repos) | Instance-specific — repos require re-auth on import |
| User accounts | Each instance has its own user table |
| Observability metrics | Instance-specific, recomputed from tasks |

---

## 4. Architecture

### 4.1 Entity Identity: `origin_id` (the core mechanism)

Every synced entity has a permanent, globally unique **`origin_id`**:

```
origin_id = "{instance_id_of_first_creator}:{entity_local_uuid_on_creator}"
e.g.        "550e8400-e29b-41d4-a716-446655440000:a1b2c3d4-..."
```

**Rules** (these four rules are the whole identity model — implement exactly):

1. **Export**: for each entity, look it up in the exporter's
   `sync_origin_map`. If found (entity was previously imported), emit the
   **stored** `origin_id`. If not found (entity was created on this
   instance), mint `"{my_instance_id}:{entity.id}"`. Child entities are
   NOT stored in the map at export time — the map records *imported*
   identity. **Exception (sync point)**: the export upserts the map row
   for the *workforce itself* (origin_id, `bundle_hash`, `last_synced`).
   Without this, a later pull-back onto a locally modified workforce has
   no `last_synced` baseline and the §4.5 conflict guarantee cannot fire.
   The 409 handler's remote-bundle export skips this upsert
   (`record_sync_point=False`) — advancing `last_synced` while reporting
   a conflict would mask that conflict on the client's retry.
2. **Import**: look up each `origin_id` in the importer's
   `sync_origin_map` (scoped to the authenticated user). Found → update
   that local entity. Not found → create new entity with a **new local
   UUID**, and record `(origin_id → new local id)` in the map.
3. **Propagation**: origin IDs are never rewritten on import. An entity
   created locally, pushed to cloud, and pulled back keeps the same
   `origin_id` the whole way — so the pull updates the local original
   instead of duplicating it (the exporter's lookup in rule 1 returns the
   stored origin, and... the original creator recognizes its own prefix —
   see rule 4).
4. **Self-recognition**: on import, if an `origin_id` has the importer's
   own `instance_id` prefix and is not in the map, resolve it directly to
   the local entity with that UUID (it originated here). This closes the
   push → cloud-edit → pull loop without requiring the creator to have a
   map entry for its own entities.

**Why this replaces export-time `bundle_ref`s** (v1 design): refs like
`agent_0` assigned at export time are not stable across exports — a
reordered query or a deleted agent shifts every index, and the remote
origin map then updates the wrong entities and deletes the rest. Local
UUIDs are stable, opaque, and free.

**Intra-bundle wiring also uses `origin_id`**: edges reference
`source_origin_id` / `target_origin_id`; agents list knowledge bases by KB
`origin_id`; tasks/conversations reference their agent by
`agent_origin_id`. One identifier, one remap table at import time.

**Fork semantics** (marketplace install): a fork is a *new* identity. The
fork operation mints fresh origin IDs (`{cloud_instance_id}:{new_uuid}`)
for every cloned entity. The buyer's pulled copy is fully independent from
the seller's original — re-pushes by the seller never touch buyer forks.

### 4.2 Bundle Format

A **WorkforceSyncBundle** is a self-contained JSON document:

```json
{
  "bundle_version": "1.0",
  "exported_at": "2026-06-12T19:00:00Z",
  "instance_id": "550e8400-e29b-41d4-a716-446655440000",
  "content_hash": "sha256:abc123...",

  "workforce": {
    "origin_id": "550e8400-...:wf-uuid",
    "name": "Rakan's Life OS",
    "description": "...",
    "runtime_mode": "claude_max",
    "config_json": {},
    "status": "active"
  },

  "agents": [
    {
      "origin_id": "550e8400-...:agent-uuid-1",
      "name": "Daily Pilot",
      "role": "coordinator",
      "instructions": "...",
      "model_provider": "anthropic",
      "model_name": "sonnet",
      "escalation_model": null,
      "max_turns": 30,
      "tools": [],
      "knowledge_bases": ["550e8400-...:kb-uuid-1"],
      "config_json": { "welcome_message": "..." },
      "position_x": 400,
      "position_y": 50
    }
  ],

  "edges": [
    {
      "origin_id": "550e8400-...:edge-uuid-1",
      "source_origin_id": "550e8400-...:agent-uuid-1",
      "target_origin_id": "550e8400-...:agent-uuid-2",
      "approval_mode": "auto_run",
      "label": "Check fitness status",
      "condition_expr": null,
      "max_runs": null,
      "task_mode": null
    }
  ],

  "knowledge_bases": [
    {
      "origin_id": "550e8400-...:kb-uuid-1",
      "name": "Finance Principles",
      "description": "Rich Dad Poor Dad notes",
      "repos": [
        { "provider": "github", "owner": "rakan", "repo": "notes",
          "default_branch": "main", "requires_reauth": true }
      ],
      "texts": [
        { "title": "Chapter 1 Notes", "content": "Assets vs liabilities..." }
      ]
    }
  ],

  "integrations": [
    {
      "origin_id": "550e8400-...:int-uuid-1",
      "plugin_name": "slack",
      "display_name": "Team Slack",
      "config_json": { "webhook_url": "***REDACTED***", "channel": "#general" },
      "redacted_fields": ["webhook_url"],
      "status": "inactive"
    }
  ],

  "tasks": [],
  "conversations": []
}
```

**Key design decisions**:

- **Schema completeness is enforced by test, not by review.** The bundle
  agent/edge schemas MUST carry every syncable model field. Verified
  against `backend/app/agents/models.py` and `workforces/models.py`:
  agents include `escalation_model`; edges include `condition_expr`,
  `max_runs`, `task_mode`. A **round-trip test** (export → import into a
  clean instance → export again → deep-compare content) is a required
  Phase 1 test; it turns future model-field drift into a CI failure
  instead of silent data loss.

- **No local UUIDs are reused by the importer.** New UUIDs are generated
  on import; the receiving instance owns its own ID space. (Local UUIDs do
  appear *inside* minted `origin_id` strings — that's identity metadata,
  not a key the importer uses for storage.)

- **`instance_id`** is a stable UUID generated once at first startup and
  stored in a **database settings row** (not `.env` — survives container
  recreation via the DB volume and is immune to user .env mistakes; not
  the URL — survives port changes).

- **`content_hash`** = `"sha256:" + hex(sha256(canonical_json(payload)))`
  where `payload` is the bundle **minus** `exported_at`, `instance_id`,
  and `content_hash` (volatile/envelope fields would defeat duplicate
  detection — two identical exports must produce identical hashes).
  Canonical JSON = keys sorted, compact separators (`,`/`:`), UTF-8,
  `ensure_ascii=False`. (RFC 8785 JCS is acceptable but sorted-compact is
  sufficient since we hash and compare only our own output.)

- **`bundle_version`** enables forward-compatible schema evolution. Import
  validates the version and rejects unknown majors with 422.

- **Knowledge `texts` are included** (stored in DB as
  `KnowledgeText.content` — verified, no file I/O needed). Repo links are
  included as metadata with `requires_reauth: true`; OAuth tokens never
  travel.

### 4.3 Identity Mapping Table

Each instance maintains a mapping table:

```sql
CREATE TABLE sync_origin_map (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       VARCHAR(36) NOT NULL,    -- scoped to user (security)
    local_id      VARCHAR(36) NOT NULL,
    origin_id     TEXT NOT NULL,            -- "{creator_instance_id}:{creator_uuid}"
    entity_type   VARCHAR(50) NOT NULL,     -- "workforce" | "agent" | "edge" | "knowledge_base" | "integration"
    bundle_hash   TEXT,                     -- content_hash of last imported bundle (workforce rows only)
    last_synced   TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (user_id, origin_id, entity_type)
);
CREATE INDEX idx_sync_origin_local ON sync_origin_map(user_id, local_id, entity_type);
```

**Why `user_id` is in the unique constraint**: Without it, a malicious
actor could craft a bundle with a forged `instance_id` to overwrite
another user's synced data. All origin lookups are scoped to the
authenticated user. The importer additionally verifies that every
resolved `local_id` belongs to the authenticated user before touching it.

### 4.4 Import Algorithm (normative — implement exactly)

```
POST /api/v1/sync/import  (body: bundle, query: force=false)

1. Enforce request limits (size, entity counts, rate limit — §4.7).
2. Validate bundle against Pydantic schema (422 on failure).
   Verify content_hash matches recomputed canonical hash (422 on mismatch).
3. Idempotency: look up workforce origin_id in sync_origin_map for this
   user. If found AND stored bundle_hash == bundle content_hash →
   return 200 with existing workforce summary (no-op).
4. Resolve workforce identity:
   a. origin map hit → UPDATE path (step 5).
   b. origin_id prefix == my instance_id and local row exists and is
      owned by this user → UPDATE path (self-recognition, §4.1 rule 4).
   c. otherwise → CREATE path (step 6).
5. UPDATE path:
   a. Conflict check (skip if force=true): compute remote_changed_at =
      max(workforce.updated_at, all agents.updated_at,
          all KB/text/integration.updated_at, all edge.created_at)
      for the existing local workforce. If remote_changed_at >
      sync_origin_map.last_synced → return 409 with body
      { "error": "sync_conflict", "remote_bundle": <current export> }.
   b. Build ref map: for every entity origin_id in the bundle, resolve
      to local id (map lookup, then self-recognition). Unresolved →
      will be created.
   c. Upsert: update resolved entities; create unresolved ones (new
      UUIDs, map rows added).
   d. Reconcile deletions: entities in sync_origin_map for this
      workforce+user but ABSENT from the bundle → delete entity and
      map row. (Bundle = complete desired state. No tombstones.)
   e. Remap references through the ref map: edge source/target,
      agent.knowledge_bases, task/conversation agent ids.
6. CREATE path: create all entities with new UUIDs, record every
   origin_id → local_id in the map, remap references as in 5e.
7. Post-conditions (both paths):
   - workforce.status = "draft" on CREATE (user activates when ready);
     status preserved on UPDATE.
   - workforce.source = "sync" on CREATE (new value; fits the existing
     32-char column alongside "web"/"sdk"/"navaia-code").
   - integrations: status = "inactive", secrets-bearing fields absent;
     collect plugin names into integrations_require_setup.
   - update sync_origin_map.last_synced = now(),
     bundle_hash = content_hash (workforce row).
8. Everything above runs in ONE database transaction. Any failure rolls
   back the entire import.
9. Respond 201 (created) / 200 (updated) with SyncImportResult.
```

### 4.5 Conflict Resolution

**Strategy**: VS Code Settings Sync model — simple and user-friendly.

| Scenario | Behavior |
|----------|----------|
| Push, remote unchanged since last sync | Overwrite remote version |
| Push, remote changed since `last_synced` (per §4.4 5a) | `409 Conflict`, body includes current remote bundle |
| Pull (marketplace purchase / fork) | Always a fresh fork — no conflict |
| Pull (own workforce, modified locally) | Same 409 pattern — works because `origin_id` propagation + self-recognition make the local import resolve to the original entities |

**Conflict timestamp definition** (required because `Edge` has no
`updated_at` — verified): `remote_changed_at = max(updated_at of
workforce, agents, knowledge bases, texts, integrations; created_at of
edges)`. Additionally, the backend's **edge delete** handler must bump
`workforce.updated_at` (a deleted edge leaves no timestamp behind) — small
backend change, listed in the task table.

**SDK behavior on 409**: the sync resource handles 409 itself (the generic
`error_from_status` mapper only carries a message — sync needs the
response **payload**). It raises `SyncConflictError` carrying both bundles:

```python
from navaia_forge import SyncConflictError

try:
    local.sync.push("wf_123", remote=cloud)
except SyncConflictError as e:
    # e.local_bundle  — what you tried to push (attached by the SDK)
    # e.remote_bundle — current cloud state (parsed from the 409 body)
    cloud.sync.import_bundle(e.local_bundle, force=True)   # accept local
    # OR: local.sync.import_bundle(e.remote_bundle, force=True)  # accept remote
```

Phase 1 does NOT attempt automatic merge. Manual resolution is fine for
configuration data that changes infrequently.

### 4.6 Credential Security

Verified: integration `config_json` is stored **plaintext** in the DB and
there is **no existing redaction logic** — this is built from scratch.

**Export behavior — deny by default**:
- ALL values in integration `config_json` are replaced with
  `"***REDACTED***"` **except** keys on a per-plugin allowlist of
  known-non-secret display fields (e.g. `channel`, `team_name`).
  Key-name heuristics ("contains key/token/secret") are NOT sufficient —
  e.g. a Slack `webhook_url` is a credential and matches no heuristic.
- Allowlists live in `backend/app/sync/redaction.py` as a
  `dict[plugin_name, frozenset[str]]`. Unknown plugin → redact everything.
- `redacted_fields` on each integration lists stripped keys so the
  importer knows what needs reconfiguring.

**Import behavior**:
- Redacted placeholder values are **dropped**, never written to the DB.
- Integrations are always created in `inactive` status.
- Import result includes `integrations_require_setup: ["slack", ...]`.

**Marketplace fork**: forks do NOT clone integrations at all (they would
carry the *seller's* account context even redacted). Buyers add their own.

### 4.7 Abuse Limits

- Import endpoint never trusts `user_id` or `instance_id` from the bundle
  for authorization. The workforce is owned by the authenticated caller.
- **Body size**: 10 MB (config-only) / 50 MB (runtime data). FastAPI does
  NOT enforce this natively — implement via `Content-Length` check +
  streaming guard in a dependency/middleware. Return 413.
- **Entity counts** (a 10 MB bundle of 100k tiny rows is still a DB-flood
  vector): max 200 agents, 1000 edges, 100 knowledge bases, 500 texts,
  100 integrations, 10k tasks, 10k messages per bundle. Return 422.
- **Rate limiting** on `/sync/import` and `/sync/export` (per-user),
  consistent with existing endpoint protections.

---

## 5. API Endpoints (Backend)

All endpoints go under `/api/v1/sync/` and require authentication
(existing JWT bearer / `X-API-Key` mechanisms — verified in
`auth/deps.py`).

### 5.1 Export

```
GET /api/v1/sync/export/{workforce_id}
```

**Query params**:
- `include_tasks` (bool, default: false)
- `include_conversations` (bool, default: false)

**Response**: `200 OK` with `WorkforceSyncBundle` JSON body.

**Auth**: `workforce.user_id == current_user.id`. Marketplace-installed
forks are owned by the buyer (verified: `install_free_listing` sets
`user_id` to buyer), so no special case is needed.

### 5.2 Import

```
POST /api/v1/sync/import?force=false
```

**Body**: `WorkforceSyncBundle`. **Behavior**: §4.4 normative algorithm.

**Responses**:
- `201 Created` (new) / `200 OK` (updated or idempotent no-op)
- `409 Conflict` — body `{ "error": "sync_conflict", "remote_bundle": {...} }`
- `413` body too large · `422` schema/hash/count violations

```json
{
  "workforce_id": "new-uuid",
  "action": "created | updated | unchanged",
  "agents":          { "created": 7, "updated": 0, "deleted": 0 },
  "edges":           { "created": 12, "updated": 0, "deleted": 0 },
  "knowledge_bases": { "created": 2, "updated": 0, "deleted": 0 },
  "integrations":    { "created": 1, "updated": 0, "deleted": 0 },
  "tasks_imported": 0,
  "conversations_imported": 0,
  "integrations_require_setup": ["slack"]
}
```

(Uniform `{created, updated, deleted}` triple per entity type — v1's
flat asymmetric fields are replaced.)

---

## 6. SDK Interface (Python)

```python
from navaia_forge import NavaiaForgeClient, SyncConflictError

local = NavaiaForgeClient(base_url="http://localhost:8001", api_key="nf_local")
cloud = NavaiaForgeClient(base_url="https://fareegi.navaia.sa", api_key="nf_cloud")

# ── Export a bundle ──────────────────────────────────────
bundle = local.sync.export_bundle("wf_123")
# Returns: WorkforceSyncBundle (Pydantic model)

# ── Import a bundle ──────────────────────────────────────
result = cloud.sync.import_bundle(bundle)            # SyncImportResult
result = cloud.sync.import_bundle(bundle, force=True)

# ── Push (export local → import to cloud, SDK makes both calls) ──
try:
    result = local.sync.push("wf_123", remote=cloud)
except SyncConflictError as e:
    result = local.sync.push("wf_123", remote=cloud, force=True)

# ── Pull (export from cloud → import to local) ──────────
result = local.sync.pull("wf_cloud_456", remote=cloud)

# ── Save/load bundle to disk ─────────────────────────────
local.sync.export_to_file("wf_123", "my_workforce.json")
local.sync.import_from_file("my_workforce.json")
```

**Implementation notes for the SDK agent**:
- `SyncResource` follows the existing `ResourceBase` pattern
  (`resources/_base.py`, `HttpClient` from `http.py`).
- 409 handling is **local to the sync resource**: catch the raw 409
  before/around the generic `error_from_status` mapping, parse
  `remote_bundle` from the body, attach the just-exported bundle as
  `local_bundle`, raise `SyncConflictError(status_code=409, message=...,
  local_bundle=..., remote_bundle=...)` (subclass of `NavaiaForgeError`).
- `push(workforce_id, remote, *, force=False, include_tasks=False,
  include_conversations=False)` = `self.export_bundle(...)` then
  `remote.sync.import_bundle(bundle, force=force)`.
- `pull(workforce_id, remote, *, force=False)` = `remote.sync.export_bundle(...)`
  then `self.import_bundle(bundle, force=force)`.

### TypeScript parity

```typescript
const local = new NavaiaForge({ baseUrl: "http://localhost:8001", apiKey: "nf_local" });
const cloud = new NavaiaForge({ baseUrl: "https://fareegi.navaia.sa", apiKey: "nf_cloud" });

const bundle = await local.sync.exportBundle("wf_123");
const result = await cloud.sync.importBundle(bundle);

await local.sync.push("wf_123", cloud);
await local.sync.pull("wf_cloud_456", cloud);
```

**Parity gap to close while here** (verified): `src/errors.ts` is missing
`ValidationError` (422), `ServerError` (5xx) — add them along with
`SyncConflictError` (409).

---

## 7. User Flows

> Topology note (design principle 7): the **SDK client** orchestrates
> every flow with two HTTP calls. The local backend and the cloud never
> connect to each other.

### 7.1 Build Locally, Push to Cloud

```
User / SDK              Local Backend              Fareegi Cloud
  │                         │                          │
  │ pip install forge-sdk   │                          │
  │ docker compose up       │                          │
  │─── create workforce ──▶│                          │
  │─── create agents ─────▶│                          │
  │─── create edges ──────▶│                          │
  │                         │                          │
  │ sync.push():            │                          │
  │─── GET /sync/export ──▶│                          │
  │◀── bundle ─────────────│                          │
  │─── POST /sync/import ──────────────────────────▶ │
  │                         │     validate · create entities · store origin map
  │◀── SyncImportResult ──────────────────────────── │
  │                         │                          │
  │ Open fareegi.navaia.sa — workforce visible in UI   │
```

### 7.2 Buy from Marketplace, Pull to Local

```
User / SDK              Local Backend              Fareegi Cloud
  │                         │                          │
  │ Browse marketplace ─────────────────────────────▶ │
  │ Install workforce ──────────────────────────────▶ │
  │                         │      install_free_listing(): fork with FRESH
  │                         │      origin_ids — agents + edges + KBs cloned,
  │                         │      integrations NOT cloned (buyer adds own)
  │ sync.pull():            │                          │
  │─── GET /sync/export (fork id) ──────────────────▶ │
  │◀── bundle ────────────────────────────────────── │
  │─── POST /sync/import ─▶│                          │
  │◀── SyncImportResult ───│                          │
  │                         │                          │
  │ Run workforce locally   │                          │
  │─── create task ───────▶│── LLM calls (local keys) │
```

### 7.3 Update and Re-Push (deletion reconciliation)

```
User / SDK              Local Backend              Fareegi Cloud
  │─── update agent ──────▶│                          │
  │─── delete agent ──────▶│                          │
  │─── add new agent ─────▶│                          │
  │ sync.push():            │                          │
  │─── GET /sync/export ──▶│  (origin_ids stable —    │
  │◀── bundle ─────────────│   derived from UUIDs)    │
  │─── POST /sync/import ──────────────────────────▶ │
  │                         │   match via origin map · update matched ·
  │                         │   create new · DELETE absent · reconcile edges
  │◀── action: "updated", agents {updated:5, created:1, deleted:1} ── │
```

### 7.4 Round Trip (push, edit on cloud UI, pull back) — no duplicates

```
1. push local→cloud      cloud maps  local_origin → cloud_uuid
2. edit agent on cloud UI
3. pull cloud→local:
   cloud export emits the STORED origin_ids (map lookup, §4.1 rule 1)
   local import: origin prefix == local instance_id → self-recognition
   (§4.1 rule 4) → updates the ORIGINAL local entities. No duplicate.
   If local was also modified since last sync → 409, user decides.
```

---

## 8. Implementation Plan

### Phase 1: Snapshot Bundle Sync (target: 1-2 weeks)

**Backend (NavaiaForge repo)** — new module `backend/app/sync/`:

| # | Task | Files | Effort |
|---|------|-------|--------|
| 1 | `instance_id`: DB settings row, generated at first startup; expose via internal helper | new `app/sync/instance.py` + migration | 0.5d |
| 2 | `sync_origin_map` migration (§4.3 schema, `user_id` in unique constraint) | `alembic/versions/` | 0.5d |
| 3 | Bundle schemas (Pydantic) — **complete** field coverage incl. `escalation_model`, `condition_expr`, `max_runs`, `task_mode`; entity-count limits as validators | `app/sync/schemas.py` | 0.5d |
| 4 | Canonical hash util (sorted keys, compact, UTF-8; excludes envelope fields) | `app/sync/hashing.py` | 0.25d |
| 5 | Export service: serialize workforce → bundle; origin_id emit rules (§4.1 rule 1); KB-ref substitution in `agent.knowledge_bases` | `app/sync/service.py` | 1d |
| 6 | Import service: §4.4 algorithm verbatim (resolve, conflict check, upsert, deletion reconciliation, ref remap, single transaction) | `app/sync/service.py` | 2d |
| 7 | Redaction module: deny-by-default + per-plugin allowlists; import drops placeholders, forces `inactive` | `app/sync/redaction.py` | 0.5d |
| 8 | Router: export + import endpoints; body-size guard (Content-Length + stream cap → 413); rate limiting | `app/sync/router.py` | 0.75d |
| 9 | Register router in `main.py` under `/api/v1` | `app/main.py` | 5min |
| 10 | Edge delete handler bumps `workforce.updated_at` (conflict-detection prerequisite, §4.5) | `app/workforces/service.py` | 0.25d |
| 11 | Extend `install_free_listing` to clone knowledge bases (KBs + texts + repo metadata, remap `agent.knowledge_bases`); fork mints fresh origin_ids; still no integrations | `app/workforces/service.py:514` | 0.75d |
| 12 | Tests: **round-trip equality** (export→import→export deep-compare), idempotent re-import, update path, deletion reconciliation, 409 + force, self-recognition pull-back (§7.4), redaction (incl. webhook_url), size/count limits, cross-user forgery rejection | `backend/tests/sync/` | 1.5d |

**SDK — Python (`packages/python`)**:

| # | Task | Files | Effort |
|---|------|-------|--------|
| 13 | Sync types: `WorkforceSyncBundle`, nested entity models, `SyncImportResult` (uniform `{created,updated,deleted}` triples) — Pydantic v2, `extra="ignore"` per house style | `navaia_forge/types.py` | 0.5d |
| 14 | `SyncConflictError(NavaiaForgeError)` with `local_bundle` / `remote_bundle` attrs | `navaia_forge/errors.py` | 15min |
| 15 | `SyncResource`: `export_bundle`, `import_bundle` (custom 409 → SyncConflictError with parsed body, §6 notes), `push`, `pull`, `export_to_file`, `import_from_file` | `navaia_forge/resources/sync.py` | 1d |
| 16 | Wire into client + package exports | `client.py`, `resources/__init__.py`, `__init__.py` | 15min |
| 17 | Tests (pytest-httpx per existing conventions): export parse, import result, push/pull two-call orchestration, 409 payload → exception attrs, file round-trip | `tests/resources/test_sync.py` | 0.5d |

**SDK — TypeScript (`packages/javascript`)**:

| # | Task | Files | Effort |
|---|------|-------|--------|
| 18 | Sync types + `SyncConflictError`; also add missing `ValidationError` (422) and `ServerError` (5xx) for parity | `src/types.ts`, `src/errors.ts` | 0.5d |
| 19 | `SyncResource` (mirror of Python incl. custom 409 handling) | `src/resources/sync.ts` | 1d |
| 20 | Wire into client + tests | `src/client.ts`, `tests/` | 0.5d |

**Infrastructure**:

| # | Task | Effort |
|---|------|--------|
| 21 | Make GHCR Docker images public (license-gated startup — enforcement verified in `distribution/enforcement.py` + `main.py` lifespan) | 15min |
| 22 | Add `docker-compose.dist.yml` to SDK repo (SETUP.md already references it) | 15min |
| 23 | Update SETUP.md with full sync workflow (push, pull, conflict resolution, integration re-auth) | 0.5d |

### Phase 2: Incremental Change Feed (only if needed)

| # | Task | Description |
|---|------|-------------|
| 24 | Add `sync_cursor` column to mutating tables | Monotonic sequence number |
| 25 | `GET /sync/changes?since={cursor}` endpoint | Returns changed entities since cursor |
| 26 | SDK `client.sync.poll(since=cursor)` | Incremental fetch |
| 27 | Background sync daemon (optional) | Auto-push changes on interval |

### Phase 3: Field-Level Merge (probably never needed)

| # | Task | Description |
|---|------|-------------|
| 28 | Per-field `updated_at` timestamps | Enable automatic merge |
| 29 | Three-way merge logic | Common ancestor + local + remote |

---

## 9. Resolved Questions

Decisions from the original review **plus the v2 code audit**:

| # | Question | Decision |
|---|----------|----------|
| 1 | Bundle size limit | 10 MB default, 50 MB with runtime data → 413. Enforced via middleware/dependency (FastAPI has no native cap). Plus per-entity count limits → 422. |
| 2 | Marketplace purchase flow | `install_free_listing` forks — but v2 audit found it clones agents+edges ONLY. Phase 1 extends it to clone KBs (task 11). Integrations never cloned. Paid listings out of scope. |
| 3 | Multi-user sync | Owner-only for Phase 1. |
| 4 | Sync frequency | Manual only for Phase 1. |
| 5 | Docker image visibility | Public images with license-gated startup (enforcement verified to exist). |
| 6 | Entity references | ~~Export-time `bundle_ref`~~ → **propagating `origin_id`** (§4.1). Fixes ref instability across exports and round-trip duplication. |
| 7 | Identity mapping scope | `user_id` in unique constraint; importer also verifies resolved local entities belong to caller. |
| 8 | Instance identifier | Stable UUID in a **DB settings row** created at first startup. |
| 9 | Deletion on re-push | Full reconciliation — origin-map entries absent from bundle are deleted. |
| 10 | Import atomicity | Single DB transaction. |
| 11 | Workforce status on import | `draft` on create; preserved on update. (`WorkforceStatus.DRAFT` verified to exist.) |
| 12 | Workforce source on import | `source = "sync"` on create — a new value alongside `web`/`sdk`/`navaia-code`; fits the 32-char column. |
| 13 | Reference remapping | Edges, tasks, conversations, **and `agent.knowledge_bases`** (v2 addition — it's a JSON list of KB IDs on the Agent model) all remap through the same origin→local map. Verify `agent.tools` carries no instance-specific IDs during implementation. |
| 14 | Knowledge texts | Included (DB-stored). Repos = metadata + `requires_reauth`; OAuth tokens never travel. |
| 15 | Conflict check endpoint | Cut. Import handles conflicts directly. |
| 16 | SDK conflict behavior | `SyncConflictError` with both bundles; **custom 409 handling in the sync resource** (generic status mapper can't carry the payload). |
| 17 | Conflict timestamp (v2) | `max(updated_at of workforce/agents/KBs/texts/integrations, created_at of edges)`; edge deletion bumps `workforce.updated_at` (task 10). |
| 18 | Hash semantics (v2) | Content-only canonical hash; excludes `exported_at`/`instance_id`/`content_hash`. Sorted-keys compact JSON. |
| 19 | Redaction policy (v2) | Deny-by-default with per-plugin allowlists. `webhook_url`-class credentials are always redacted. Placeholders dropped on import. |
| 20 | Sync topology (v2) | SDK-orchestrated client-side; backends never talk to each other. |

---

## 10. Success Criteria

Phase 1 is complete when:

- [ ] A user can `docker compose up` locally using files from the SDK repo
- [ ] They can create a workforce with agents and edges via the SDK
- [ ] They can `sync.push()` to Fareegi and see it in the cloud UI
- [ ] They can install a marketplace workforce on Fareegi and
      `sync.pull()` it locally — **including its knowledge bases**
- [ ] Re-pushing an updated workforce updates (not duplicates) on cloud
- [ ] Deleting an agent locally and re-pushing removes it on cloud
- [ ] **Round trip**: push → edit on cloud → pull updates the local
      original (no duplicate workforce)
- [ ] **Round-trip equality test passes**: export → import → export
      produces identical content (proves zero field loss)
- [ ] Integration secrets (including webhook URLs) never appear in bundles
- [ ] Two identical exports produce identical `content_hash` values
      (idempotent re-import is a no-op)
- [ ] Import is atomic — partial failures roll back cleanly
- [ ] `SyncConflictError` carries both bundles when cloud was modified
      since last push
- [ ] Oversized bundles (size or entity count) are rejected with 413/422
- [ ] A bundle referencing another user's origin IDs cannot touch that
      user's data (forgery test)
- [ ] All SDK methods have tests (Python + TypeScript)
- [ ] SETUP.md documents the full flow end-to-end

# SDK ⇄ Platform Mismatch — `tasks.retry()` hits a non-existent route

**Date:** 2026-08-27 · Source: NavaiaForge `PLATFORM-BUG-REPORT-2026-08-25` (§7)
**Status:** ✅ SDK side fixed in **0.2.4** (JS + Python) — ⏳ still gated on the platform route.

## Update (2026-08-28) — SDK changes shipped in 0.2.4
- **Python parity gap closed:** `client.tasks.retry()` did not exist at all (the README advertised
  it but the method was missing → `AttributeError`). It is now implemented in
  `packages/python/navaia_forge/resources/tasks.py` against `POST /tasks/{id}/retry`.
- **Typed 409:** both clients now raise a typed `TaskNotRetryable` (exported from the package)
  instead of a bare 4xx when the task is not in a retryable state.
- **JS `retry()`** rewritten to catch the 409 and surface `TaskNotRetryable`; `dist/` rebuilt.
- **Tests added:** JS `tests/tasks.test.ts` (success → `pending` + `retry_count++`, 409 → typed
  error) and Python `test_retry_task_resets_to_pending` / `test_retry_non_retryable_task_raises_typed_error`.
- **READMEs** document the retry semantics + the new error; versions synced to 0.2.4 (JS had
  drifted at 0.2.0). `.env.example` / compose note that retry needs a backend >= 0.2.4.

⚠️ **Still do not rely on `retry()` in production until the platform ships `POST /tasks/{id}/retry`.**
Until then the call 404s (surfaced as `NotFoundError`), exactly as before.

## What's wrong
The SDK exposes `tasks.retry(taskId)` which POSTs `/tasks/{taskId}/retry`, but the NavaiaForge
backend has **no such route** — the call returns **404**.

**Evidence (SDK side):**
- JS source: `packages/javascript/src/resources/tasks.ts:84-85`
  ```ts
  retry(taskId: string): Promise<Task> {
    return post<Task>(this.config, `/tasks/${taskId}/retry`);
  }
  ```
- Also compiled into `packages/javascript/dist/index.js:1042` / `index.cjs:1101`.
- Advertised in both READMEs (`packages/python/README.md:96`,
  `packages/javascript/README.md:118`) as a supported task-lifecycle verb.
- `retry_count` field already exists on the Task type (`packages/python/navaia_forge/types.py:247`,
  JS `client-*.d.ts:173`).

**Evidence (platform side):** a grep of `backend/app/` in NavaiaForge finds `approve`, `reject`,
`cancel`, `delete`, `bulk` routes on the tasks router (`app/tasks/router.py:151-238`) but **no
`/retry`**. So every `retry()` call has always 404'd.

## The fix (two repos, ship together)
The platform will **add** the route (retry is genuinely useful — chosen over deleting the SDK
method). Tracked in `NavaiaForge/docs/PLATFORM-BUG-REPORT-2026-08-25-FIXES.md` §7:

```
POST /tasks/{task_id}/retry   → resets a FAILED/CANCELLED task to PENDING, bumps retry_count,
                                 owner-scoped, 409 if the task is not in a retryable state.
```

**SDK-side action items (once the platform route is merged):**
1. **Verify the path + verb match exactly** — `POST /tasks/{taskId}/retry`, no body (or match
   whatever the platform finalizes). Keep JS and Python clients identical.
2. **Match the semantics in the docstring/README** — retry only applies to failed/cancelled
   tasks; the SDK should surface the platform's 409 as a clear error (e.g. `TaskNotRetryable`)
   rather than a bare HTTP error.
3. **Add a test** hitting a mock `/tasks/{id}/retry` that asserts the returned `Task` is `PENDING`
   with an incremented `retry_count`; add a 409 case for a running task.
4. **Rebuild `dist/`** — the compiled bundles (`dist/index.js`, `dist/index.cjs`, `*.d.ts`)
   carry the current call and must be regenerated from `src/` after any change.
5. **Python parity check** — confirm the Python client exposes `retry()` against the same path
   (README lists it; verify the resource implementation matches JS before release).

⚠️ **Do not ship the SDK change before the platform route exists**, or `retry()` keeps 404'ing.
Coordinate the two PRs; bump the SDK version only after the platform deploy that adds the route.

## Test (SDK)
- Mock server with `POST /tasks/{id}/retry` → `tasks.retry(id)` resolves to a `Task` with
  `status="pending"` and `retry_count` incremented.
- Mock returns 409 → SDK raises a typed, readable error (not a generic 4xx).
- JS and Python clients produce byte-identical request lines for the same call.

---

# N1 — Missing resource: `pipelines`

**Status:** ✅ Implemented in **0.2.4** (JS + Python). **Source:** consolidated issue list (N1).

## Update (2026-08-28) — `pipelines` resource added in 0.2.4
- **New resource, both clients:** `nf.pipelines` / `client.pipelines` with `list`, `get`,
  `create`, `update`, `delete`, `run`, `listRuns`/`list_runs`, `reportRun`/`report_run` — mirroring
  the platform routes below.
- **New files:** `packages/javascript/src/resources/pipelines.ts`,
  `packages/python/navaia_forge/resources/pipelines.py`.
- **Types added:** `Pipeline` + `PipelineRun` (JS also `PipelineCreate` / `PipelineUpdate` /
  `PipelineRunReport`) in `types.ts` / `types.py`, exported from both packages.
- **Registered** on both clients next to `tasks`; **README** resource tables list `pipelines`.
- **Tests:** JS `tests/pipelines.test.ts` + Python `tests/resources/test_pipelines.py` (list — both
  envelope and bare-array shapes — `run`, `list_runs` with `limit`, `report_run`). `dist/` rebuilt.

> ⚠️ **Confirm response shapes before relying on typed fields.** The `Pipeline` / `PipelineRun`
> models were mirrored from the documented routes, not verified against `app/pipelines/schemas.py`.
> Both models ignore unknown fields (permissive), and list unwrapping tolerates bare-array **or**
> `{items,total}` responses, so calls won't crash on shape drift — but field names/optionality
> should be reconciled with the backend schema before they're treated as a stable contract.

## What's wrong
The **platform has a full pipelines API** — `app/pipelines/router.py` mounts, at `/api/v1`:
`GET /pipelines`, `GET /workforces/{wf_id}/pipelines`, `POST /pipelines`, `GET/PATCH/DELETE
/pipelines/{id}`, `POST /pipelines/{id}/run`, `POST/GET /pipelines/{id}/runs` — and the web app uses
all of it (sidebar link + pages + hooks).

**The SDK has no `pipelines` resource.** The resource set is
`agents, auth, conversations, integrations, knowledge, marketplace, observability, setup, sync, tasks,
templates, tools, workforces` — no pipelines in either the JS (`packages/javascript/src/resources/`)
or Python (`packages/python/navaia_forge/resources/`) client. So pipelines are **unreachable
programmatically** — you can only touch them through the web UI.

> Note: the original bug report's §7 aside "`/pipelines` is absent" was true **of the SDK**, not the
> platform API — the routes exist; the SDK just never wrapped them.

## The fix — add a `pipelines` resource (JS + Python)
Mirror the REST surface, following the existing `tasks` resource as the template.

**New files**
- `packages/javascript/src/resources/pipelines.ts`
- `packages/python/navaia_forge/resources/pipelines.py`

**Methods (both clients, identical semantics)**
| Method | Route |
|---|---|
| `list(workforceId?)` | `GET /pipelines` or `GET /workforces/{wf_id}/pipelines` |
| `create(body)` | `POST /pipelines` |
| `get(id)` | `GET /pipelines/{id}` |
| `update(id, body)` | `PATCH /pipelines/{id}` |
| `delete(id)` | `DELETE /pipelines/{id}` |
| `run(id)` | `POST /pipelines/{id}/run` |
| `listRuns(id, limit?)` | `GET /pipelines/{id}/runs` |
| `reportRun(id, body)` | `POST /pipelines/{id}/runs` (external-runner ingest) |

**Also:**
1. Register the resource on the client (JS `client.ts` / Python client `__init__`), next to `tasks`.
2. Add `Pipeline` / `PipelineRun` types to `types.ts` and the Python `types.py`, matching the
   platform's `PipelineResponse` / `PipelineRunResponse` / `PipelineDetailResponse` schemas.
3. Add a `client.pipelines` row to both READMEs' resource tables.
4. **Rebuild `dist/`** (JS bundles are checked in).

## Test (SDK)
- Mock `GET /pipelines` → `pipelines.list()` returns typed `Pipeline[]`.
- `pipelines.run(id)` POSTs `/pipelines/{id}/run` and returns a `PipelineRun`.
- JS and Python produce identical request lines per method; READMEs list `pipelines`.

⚠️ Ship after confirming the platform response shapes (`app/pipelines/schemas.py`) so the SDK types
match exactly.

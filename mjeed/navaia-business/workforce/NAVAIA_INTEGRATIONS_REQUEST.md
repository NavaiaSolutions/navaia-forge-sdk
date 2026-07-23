# Request to Navaia — fix `/integrations` update/delete (HTTP 500) + purge two stale rows

**Workforce id:** `131bb52f-e5eb-44ad-8134-03dc6908b485` (backend `fareegi.navaia.sa`)
**Date:** 2026-07-13
**Impact:** our agents' **in-task CRM tool is currently broken** — see §2. This is the top blocker
for the outreach pipeline running through the agents (scripts still work as a stopgap).

---

## 1. Backend bug — `PUT` and `DELETE` on `/integrations/{id}` both return HTTP 500

The integration endpoints only support CREATE. We cannot edit or remove an integration via the
public API, so misconfigured/duplicate rows can't be cleaned up client-side.

Verified live 2026-07-13 (same result via the SDK and raw HTTP, valid `x-api-key`):

| Method | `/api/v1/integrations/{id}` | Result |
|--------|------------------------------|--------|
| `PATCH` | update | **405 Method Not Allowed** |
| `PUT`   | update (SDK `integrations.update`) | **500 Internal Server Error** (empty body) |
| `DELETE`| remove (SDK `integrations.delete`) | **500 Internal Server Error** (empty body) |
| `POST`  | create | 200 ✅ (the only working verb) |

This also explains earlier stuck records (e.g. the inactive Hunter row that couldn't be removed).

**Ask 1:** fix `PUT` and `DELETE` on `/integrations/{id}` (or expose a working update/delete path).

---

## 2. Consequence — CRM is broken because a stale duplicate can't be removed

Our `twenty` integration was pointing at the wrong host (`navaia-business.twenty.com`). Because
`PUT` 500s, we couldn't correct it in place, so we **created** a correct one
(`crm.navaia.sa`, id `a3f5ac89-6e6b-4b38-b8d0-0d4410fb5538`) and tried to delete the old one —
but `DELETE` 500s, so the wrong row survives.

There are now **two `twenty` integrations**, and the toolbridge resolves to the **wrong (old) one**.
Evidence — a read-only CRM probe task fails:

```
Twenty CRM returned 401 Unauthorized
{"statusCode":401,"messages":["Workspace not found"],"error":"WORKSPACE_NOT_FOUND"}
[WAITING:BLOCKED]
```

…even though the **same credential works when called directly**. Our `TWENTY_TOKEN` is a valid
Twenty **API key** (`type=API_KEY`, carries `workspaceId`, expires 2027) and returns **HTTP 200**
against `https://crm.navaia.sa` on both REST (`/rest/companies`) and GraphQL. So the token, host,
and key-type are all correct — the failure is purely that the runtime uses the stale row.

**Ask 2:** delete these two stale rows for workforce `131bb52f-…` (directly in the DB is fine):

| plugin | id | why remove |
|--------|----|-----------|
| `twenty`   | `5961b579-e629-4483-a132-a5a8b40c095a` | wrong host `navaia-business.twenty.com`; superseded by `a3f5ac89-…` (`crm.navaia.sa`) |
| `telegram` | `f3369460-a43e-45e2-a34c-291f5f31254e` | empty duplicate; the real one is `eb68017e-…` (has bot_token + chat_id) |

After removal, exactly one `twenty` (`crm.navaia.sa`) and one `telegram` should remain.

---

## 3. Optional — confirm toolbridge resolution when duplicates exist

When two integrations share a `plugin_name`, which does the toolbridge pick (oldest? newest?
first `active`?)? If it were "most-recent-active," our create-based workaround would have fixed the
CRM without a delete. Documenting this would let us self-serve around the DELETE bug until Ask 1
lands.

---

## 4. What's NOT blocked (so you know the scope)

- Direct-API access to CRM works: our scripts (`import_all_leads.py`, `dump_crm.py`, the Telegram
  bot's lead-status updates) call `crm.navaia.sa` with the token directly and succeed. Only the
  **agents' in-task CRM tool** (via the toolbridge integration) is affected.
- All 7 agents, tasks, conversations, and the other integrations (Baian, Snov, Zoho, Telegram) are
  healthy. Runtime is `navaia_code` (Kimi).

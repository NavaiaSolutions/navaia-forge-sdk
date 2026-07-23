# Request to Navaia — dashboard cannot answer a waiting task (HITL gap in the UI)

**Workforce id:** `131bb52f-e5eb-44ad-8134-03dc6908b485` (backend `fareegi.navaia.sa`)
**Date:** 2026-07-14
**Impact:** tasks that pause on `waiting_question` / `waiting_plan` **cannot be resumed from the
Fareegi dashboard at all** — the operator must use an API client. This blocks the intended
"assign a task in the dashboard → approve in the dashboard → read the report" loop.

---

## What's missing

The backend supports answering a paused task (verified live, used daily by our tooling):

```
POST /tasks/{id}/approve
{"response": "<operator's answer text>"}
```

- The JSON **body is required** — a body-less approve returns **422** (`body Field required`).
- `waiting_question` and `waiting_plan` are accepted; `waiting_blocked` returns 400 (must re-run).
- The response text is stored as `metadata_json.approval_response` and the worker resumes the
  agent with it as the pending answer.

But the **dashboard UI exposes no control for this**: a task sitting in `waiting_question`
shows its question in the result text, and there is nothing to click or type to answer it.
The chat panel creates *conversations* — a separate object that never touches the task.

## Why it matters

Our outreach pipeline hard-stops at a human-approval gate on every send (the task enters
`waiting_question` carrying the rendered messages). The operator is supposed to be able to
answer from **any** surface. Today the only working surfaces are our own Telegram bot and a
local console — the dashboard, the most natural place, is the one surface that can't.

## Ask

On any task in `waiting_question` / `waiting_plan`, show the question (task result) with an
**answer text box + Approve button** that submits `POST /tasks/{id}/approve {"response": …}`.
For `waiting_blocked`, a **Re-run** button (reject + recreate) would match the backend's
semantics. That single UI element makes the dashboard a complete operator console.

# Postmortem — 2026-07-14: every fault, its root cause, and what now prevents it

The day started with a pipeline batch frozen in `pending` and ended with the first real
outreach delivered: **30 WhatsApp + 20 emails, 0 send errors, all 30 leads statused in the
CRM**. Between those two points, nine distinct faults surfaced. Each is documented here
with its evidence, root cause, the fix that shipped, and what residual risk remains.

The single meta-lesson, which now shapes the whole pipeline (`scripts/outreach.py`):
**every fault came from giving an LLM authority over a step that should have been
deterministic** — rendering, routing, lifecycle signaling, status updates. Scripts now hold
that authority; the cloud agent executes only the one step that must live there (the
WhatsApp/Meta token exists only in the cloud env).

---

## Fault 1 — Tasks frozen in `pending` for hours (13:12–14:32Z)

**Symptom.** Six tasks submitted after 13:12Z never started: no log events, no status
change, no error. The batch task sat `pending` from 13:39 until 14:32.

**Root cause.** The cloud workforce (`navaia_code` runtime) billed an OpenRouter key with a
**rolling-24h $4 spending cap** (`limit_reset: "daily"`; verified arithmetically:
`usage_daily + limit_remaining = 4.000` exactly). The morning's runs exhausted the window
at ~13:12 → every LLM call failed → the worker could not start any task. With
`navaia_code`, a dead credential produces **silent stalls** (documented in FAREEGI.md:
"tasks fail silently: the task just never progresses"). Tasks resumed at 14:32 only because
old usage aged out of the rolling window — not because of any fix.

**Compounding discovery.** The workforce provider key **cannot be set via API**:
`PUT /workforces/{id}` with `provider_key` returns 200 OK but silently ignores the field
(`updated_at` unchanged, old key kept billing). Every plausible key endpoint 404s. The key
is set only in the Fareegi dashboard. The old key's account was also nearly drained
($1.59 of $165 left).

**Fix.** Operator installed his own key via the dashboard (verified empirically: a probe
task billed the new key and the old key's usage froze). Diagnostic recipe recorded: when
tasks sit `pending` with no logs, check `GET https://openrouter.ai/api/v1/auth/key` for
`limit_remaining` first; to prove which key a cloud runs on, compare `usage_daily` deltas
across candidate keys during a run.

**Residual risk.** The operator's key has its own limits; the same silent stall returns if
it runs dry. There is still no API/alerting surface for this — a balance check before batch
submission would be a worthwhile addition to `outreach.py`.

---

## Fault 2 — An outreach task auto-routed to Rashid (Strategy)

**Symptom.** A completed outreach task spawned "[Routed] Outreach…" assigned to Rashid, who
correctly refused ("this is outside my scope") and blocked.

**Root cause.** The backend's `route_task()` runs on every task completion and evaluates
each outgoing edge of the finishing agent. The default edge condition is `"mention"` — a
**case-insensitive substring search of the target agent's NAME in the result text**. A lead
was named **"Al Rashid Trading & Contracting Co."** → substring "Rashid" matched the
Ahmed→Rashid "Strategy tasks" edge. A company name collided with an agent name; nothing
more.

**Fix.** All 15 edges now carry `condition_expr = contains:[route:<agent>]` (verified
persisted). Routing fires **only** when an agent deliberately writes a literal
`[ROUTE:NAME]` marker. Trap discovered en route: the documented `"never"` condition is
UNRECOGNIZED by `_evaluate_condition` and falls through to `return True` (= always route) —
never use it; disable edges with a `contains:` marker instead.

**Residual risk.** New edges created via dashboard default back to `"mention"` — any new
edge must get an explicit condition.

---

## Fault 3 — HITL gates printed as text, then the task marked DONE

**Symptom.** Twice, Ahmed rendered every message, wrote "HITL APPROVAL GATE" with the full
approval question — and the task completed. Nobody was ever asked; with Fault 2, the
completion text then fed the router.

**Root cause.** The runtime's entire lifecycle API is **literal end-of-output markers**
(`[DONE]`, `[WAITING:QUESTION]`, `[WAITING:PLAN]`, `[WAITING:BLOCKED]`, `[ERROR]` —
`app/tasks/service.py handle_signal`). The instructions ordered agents to "enter the
waiting_question state" but **no prompt anywhere documented the marker that does it** —
zero mentions of `[WAITING:QUESTION]` in any agent file. An order without its mechanism is
dead text; the model ended with `[DONE]` and the gate died.

**Fix.** `_shared_preamble.md` gained `<runtime_signals>` — the full marker contract,
shipped to all 7 agents via `deploy_agents.py` (verified). Task templates name the literal
marker at the gate step. Empirically confirmed working: the first per-vertical task after
the fix paused in `waiting_question` correctly.

**Residual risk.** Marker compliance is still LLM behavior, so `scripts/outreach.py`
removes the in-task gate entirely for the standard pipeline (approval happens locally,
before any cloud task exists).

---

## Fault 4 — "Why did Ahmed do Lina's work?"

**Symptom.** Ahmed (GM) generated all the outreach copy himself instead of delegating to
Lina (Marketing).

**Root cause — three layers.** (1) **No delegation mechanism exists in the task runtime**:
agents' toolboxes contain only twenty/zoho/snov/baian — there is no "assign to teammate"
tool; the CLI-side orchestration (Agent/Task tools) does not exist inside cloud task
execution. The only handoff is edge-routing, which fires at task *completion* — useless
mid-task. (2) The task description **explicitly told him to**: "if delegation is
unavailable, fill the templates YOURSELF" — a fallback deliberately baked in by earlier
sessions that had already discovered layer 1. (3) Ahmed's deployed instructions ("you never
do domain work yourself") described the CLI environment, not the task runtime — an
instructions/reality mismatch.

**Fix.** Ahmed's payload rewritten to match reality (route only at task end via
`[ROUTE:NAME]` with compact payloads; do embedded-template work in-task when the task says
so). The `[ROUTE:]` mechanism now makes real sequential delegation possible when wanted.

**Residual risk.** Routed handoffs truncate at 12,000 chars — large content must never
travel across a route (pointers only). Documented in the preamble.

---

## Fault 5 — Renders truncated mid-word; the 31-lead batch could never gate

**Symptom.** Three runs produced results cut off mid-sentence at ~17.7–18.1k chars after
~18 of 31 leads, each ending signal-less (→ recorded as DONE by default).

**Root cause.** A 31-lead × 2-channel render (~30k+ chars) exceeds the runtime's
**per-response output budget (~18k chars observed)**. The model is cut before it can write
the closing marker, so the task can neither pause nor route.

**Fix.** Outreach fires **per-vertical** (7–13 leads ≈ 5–9k chars — comfortable). The
definitive fix is `outreach.py`: rendering is local, so cloud output size no longer
constrains batch size; the send checklist per vertical is compact.

---

## Fault 6 — Approved gates looped: approve → re-ask → approve → re-ask (×4)

**Symptom.** Every approval delivered to the three per-vertical gates resulted in the agent
re-rendering all messages and re-asking the same question. Four approvals were consumed
with zero forward progress.

**Root cause.** On resume, the runtime replays the task description + transcript and asks
the model to continue. The task steps said "render → gate"; nothing told the model what a
*resumed* task looks like. So it re-executed the steps from the top — dutifully ending at
the gate again. Task descriptions are frozen at creation, so already-running tasks couldn't
pick up the fix.

**Fix.** (1) Task templates now carry a **RESUME RULE**: "when the transcript already
contains the operator's answer, the gate is OVER — do not re-render, do not re-ask; go
directly to the send step." Console approve-texts say the same. (2) For the three stuck
tasks: `scripts/send_approved.py` bypassed the loop by handing each vertical's
operator-approved render verbatim to Tariq as a **direct send task** — which executed
30/30. (3) `outreach.py` eliminates the resume entirely.

---

## Fault 7 — `tasks.reject` did not stop a running task (near-miss)

**Symptom.** The contracting task carrying the typo template was rejected (status
confirmed `cancelled`) — yet it kept executing, "completed" 3 minutes later overwriting the
cancel, and routed a send job to Tariq. The operator's "reject all" answer to that rogue
task was then swept by the console's blanket approve-all.

**Root cause.** Reject/cancel only flips the DB status; **the in-flight runtime execution
is not killed**. When it finishes, `handle_signal` writes the terminal status over the
cancel, and routing runs. Harmless this time by luck: the routed Tariq run happened to have
no tool access and the 12k-truncated handoff had lost the lead data, so it dead-ended
without sending.

**Fix (procedural).** Treat reject as safe **only for parked tasks** (pending/waiting).
For an in-progress task, assume it will finish; make its completion harmless (deterministic
edges mean nothing routes without an explicit marker — this alone removes most of the blast
radius). Recorded in memory and the change log. Backend-side kill is Navaia's to build.

---

## Fault 8 — "فريق نفايا": the brand typo in every contracting WhatsApp

**Symptom.** Every contracting WhatsApp render closed with `عبدالمجيد الوردي - فريق نفايا`
— the brand misspelled without the ڤ (reads like "waste").

**Root cause.** The typo is **inside the Meta-approved template's locked fixed text**
(`navaia_mj_contracting_t1`, closing line `{{5}} - فريق نفايا`). It was submitted to Meta
that way and approved. Meta forbids editing approved bodies, and agents are (correctly)
required to reproduce fixed text verbatim — so every render faithfully copied the typo.
Not an agent fault: a submission-time QA miss, frozen by Meta's approval.

**Fix.** `navaia_mj_contracting_t1_v2` (id `859187770325647`) submitted with the clean
closing (`{{5}}` + `شاكراً لكم`), approved same day; `04_outreach_templates.md` switched so
every parser/task now uses `_v2`. The old `_t1` must never be sent again and should be
deleted after `_v2` sends are verified (use `manage_wa_templates.py`).

**Residual risk / rule.** Any future template submission must be proofread
character-by-character BEFORE submission — approval freezes typos permanently.

---

## Fault 9 — In-task tools flaky at send time

**Symptom.** (a) Baian's send tool returned Graph API 404 in **every** send run (cached
phone-number id). (b) The in-task CRM tool was available in one run (RE — updated 13/13 via
GraphQL) but demanded a missing key in the other two (contracting, training), despite the
2026-07-14 morning probe passing.

**Root cause.** (a) Baian's tool trusts a stale cached phone-number id; the current id
(`938243176048092`) must be discovered per-run via `GET /{WABA_ID}/phone_numbers`. (b) CRM
tool provisioning at runtime is nondeterministic per-run — cause unknown, backend-side
(worth raising with Navaia).

**Fix.** (a) The direct-Graph fallback (discover id → POST template payload) is written
into every send task as the de-facto primary — it carried all 30 sends. (b) CRM updates are
**removed from cloud tasks entirely**: `outreach.py` parses the send report and PATCHes
`crm.navaia.sa/rest/people/{id}` locally with `TWENTY_TOKEN` (applied 17/17 for the day's
stranded updates).

---

## The structural answer: `scripts/outreach.py` (script authority)

One command runs the whole loop with scripts in charge and the operator approving fast:

1. **Select** — deterministic CRM query (Mjeed's `Not Contacted`, chosen verticals).
2. **Render locally** — templates verbatim + `lina_compose` token logic (no cloud LLM →
   no loops, no truncation, no improvised subjects; optional `--llm-pain` uses the
   operator's own key for novel pain lines only).
3. **Approve fast** — compact terminal table + full render in `outreach_render.md`;
   Enter = all, numbers = skip, q = abort. What is approved is byte-exact what is sent.
4. **Send** — one literal-checklist task per vertical to Tariq (exact Graph payloads,
   exact email subject/body, no gate, no judgment, ends `[DONE]`) — the only cloud step,
   because the Meta token lives only there. This pattern went 30/30 on day one.
5. **Status + report** — the script parses the machine-readable per-lead report and
   applies CRM updates locally, then prints totals.

What each old fault maps to: 1→pre-flight key check is the remaining TODO; 2/3/4/6→no
in-cloud gate or routing in the critical path at all; 5→local render, size-free;
7→nothing to cancel mid-flight; 8→`_v2` templates parsed from the one source of truth;
9→direct-Graph instructions + local CRM writes.

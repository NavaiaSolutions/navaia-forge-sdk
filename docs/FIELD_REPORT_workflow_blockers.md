# Field report — end-to-end workflow blockers, with suggested fixes

**Scope:** bugs only. This report packages every reproducible issue we hit while operating a
production workforce through this SDK, the REST API, and the dashboard over an extended
period — mapped to the phase of the standard workflow each one blocks, with a suggested fix
per item. Two of the findings are SDK-level and are **fixed in this PR** (see §4.1, §4.2);
the rest are backend / runtime / dashboard items for the platform team.

Everything here is written generically: the findings apply to any workforce, regardless of
its domain. Where we worked around an issue, the workaround is described only in general
terms — the point of each entry is the platform-side fix, not our mitigation.

---

## 1. The reference workflow

The workflow every finding below is mapped to:

```
operator ── create task (dashboard / SDK / API) ──▶ ORCHESTRATOR agent (the workforce's GM)
                 │                                        │  decomposes, delegates per specialty
                 │                                        ▼
                 │                               specialist agents
                 │                                        │  integration tools (CRM, email,
                 │                                        │  messaging, knowledge bases, …)
                 │                                        ▼
                 │            [HITL GATE] task enters waiting_question / waiting_plan
                 │                        carrying the rendered output for review
                 │◀── operator answers (POST /tasks/{id}/approve {"response": …}) ──┘
                 ▼
          agent resumes → final report in task.result
```

A principle this report assumes throughout: **a job should be created against the one agent
responsible for orchestrating it** (the workforce's GM/orchestrator), which then reaches
specialists. Several findings below are about what happens when that either isn't possible
or isn't enforced.

## 2. Runtime modes — how orchestration actually behaves in each

The worker hands each task to a runtime with `model=agent.model_name`. The three modes
behave very differently, and several bugs only make sense against this matrix:

| Runtime mode | Honors `agent.model_name` | Tool-call reliability | Cross-agent orchestration |
|---|---|---|---|
| `claude_max` (Claude CLI) | **No** — runs its own model regardless of the agent's configured model | good | none in-task |
| `claw_code` (multi-model CLI) | Yes | some models emit **malformed JSON on complex tool calls** (multi-line bodies especially) | none in-task |
| `navaia_code` (platform CLI) | Yes | same model-dependent JSON fragility | partial: an orchestrator can spawn "[Routed]" tasks to teammates, but the routed specialist has **no way back** (see §4.8) |

Consequences observed:

- Under `claude_max`, a workforce configured for a non-Anthropic model silently runs on a
  different model than configured. **Suggested fix:** refuse the assignment (or warn loudly)
  when the runtime cannot honor the agent's model, instead of substituting silently.
- Malformed tool-call JSON from some models means complex multi-step tool work fails
  intermittently. **Suggested fix:** runtime-side JSON validation + one automatic repair/retry
  before surfacing a failure to the agent.

## 3. What each surface can and cannot do today

| Capability | SDK / API | Dashboard | In-task agent |
|---|---|---|---|
| Create a task (to the orchestrator or a specialist) | ✅ | ✅ | partial ("[Routed]" spawn, orchestrator only) |
| Watch progress | ✅ status; lifecycle `logs` were dropped by the SDK model (fixed in this PR §4.2); no step-level events exist (§4.13) | ✅ status | — |
| **Answer a waiting task (HITL)** | ✅ endpoint works — but the SDK method was broken (fixed in this PR §4.1) | ❌ **no UI at all** (§4.5) | — |
| Resume a `waiting_blocked` task | ❌ 400 — recreate only (§4.6) | ❌ | ❌ |
| Reach a teammate agent | — | — | ❌ from a specialist task (§4.8) |

The dashboard's chat panel creates *conversations* — a separate object with no relationship
to tasks — so it is not a substitute for the missing answer UI.

## 4. Findings

Each finding: **Observed → Impact → Suggested fix.**

### 4.1 SDK: `tasks.approve()` sends no body → 422 on every waiting task *(fixed in this PR)*

- **Observed:** the backend requires a JSON body on `POST /tasks/{id}/approve`; a body-less
  POST returns `422 body Field required`. The SDK method posted without a body, so *every*
  `approve()` call failed.
- **Impact:** the HITL gate — the core human step of the workflow — was unusable through the
  SDK; clients had to hand-roll the HTTP call.
- **Fix (this PR):** `approve()` always sends a JSON body and gains `response=` to deliver
  the operator's answer for `waiting_question`/`waiting_plan` (without text, agents tend to
  re-ask). Tests added.

### 4.2 SDK: `Task` model drops the `logs` field *(fixed in this PR)*

- **Observed:** `GET /tasks/{id}` returns a `logs` array of lifecycle events
  (submitted / started / waiting / completed / failed) that the SDK's `Task` model silently
  discarded (a matching `TaskLog` model already existed but was unused).
- **Impact:** SDK users cannot observe when a task started/paused/finished without raw HTTP.
- **Fix (this PR):** `Task.logs: list[TaskLog]`. Test added.

### 4.3 Backend: `/integrations/{id}` — `PUT` and `DELETE` return 500, `PATCH` 405

- **Observed:** only CREATE works on integrations. Updating a misconfigured integration or
  deleting a duplicate is impossible through the API (verified via both SDK and raw HTTP).
- **Impact:** misconfigured/duplicate integration rows accumulate and cannot be cleaned up
  client-side; combined with §4.4 this can break an integration's tools entirely, with no
  self-service recovery (a manual database purge was ultimately required).
- **Suggested fix:** fix `PUT`/`DELETE` (or expose any working update/delete path).

### 4.4 Backend: duplicate integrations resolve to the stale row

- **Observed:** with two integration rows of the same plugin (an inevitable state given
  §4.3 — the only repair path is "create a corrected copy"), the in-task toolbridge resolves
  to the **old, misconfigured** row. Agents' tool calls fail (e.g. auth errors against the
  wrong host) even though a fully valid row exists.
- **Impact:** a single stale row silently disables the plugin's tools for every agent.
- **Suggested fix:** resolve to the most recently updated *active* row — and/or enforce
  uniqueness per (workforce, plugin) at create time.

### 4.5 Dashboard: no way to answer a waiting task

- **Observed:** a task in `waiting_question` shows its question in the result text, but the
  dashboard offers no control to answer it. The chat creates conversations, which never touch
  tasks. The backend endpoint (`POST /tasks/{id}/approve {"response": …}`) works.
- **Impact:** the "create in the dashboard → approve in the dashboard" loop is impossible;
  operators must run an API client just to answer their own workforce.
- **Suggested fix:** on `waiting_question`/`waiting_plan`, render an answer box + Approve
  button wired to the existing endpoint (body included — see §4.1); on `waiting_blocked`, a
  Re-run button (reject + recreate) matching backend semantics.

### 4.6 Backend: `waiting_blocked` is a dead end

- **Observed:** blocked tasks can be neither approved nor answered (400 "not in a waiting
  state") and do **not** resume when the blocking dependency later resolves. The only path is
  manual re-creation.
- **Impact:** any transient blocker permanently kills the task; long pipelines lose all
  progress.
- **Suggested fix:** allow answering a blocked task, or provide a first-class re-run that
  preserves task identity/history.

### 4.7 Runtime: agents complete tasks with open questions — the gate silently bypassed

- **Observed:** instead of entering `waiting_question`, an agent may end its run with the
  question embedded in the result text and the task marked `done`. From every surface this is
  indistinguishable from success until a human reads the result.
- **Impact:** approval gates get skipped without anything failing; the operator's answer has
  nowhere to go (the task is terminal).
- **Suggested fix:** make the ask/pause mechanism a hard contract of the runtime — e.g. the
  worker detects an interrogative hand-back (or requires an explicit `done`/`ask` signal) and
  maps it to `waiting_question` instead of `done`. Prompt-level discipline helps but cannot be
  the only enforcement.

### 4.8 Runtime: specialists cannot reach teammates; routed tasks block forever

- **Observed:** (a) a task assigned **directly to a specialist** bypasses the orchestrator
  entirely — the specialist has no mechanism to invoke a teammate it knows by name from its
  instructions. (b) When the **orchestrator** routes a sub-task ("[Routed]" task) to a
  specialist, that specialist also cannot call back or hand off; one such task ended in
  `waiting_blocked` "pending <teammate>" — which per §4.6 is unrecoverable.
- **Impact:** multi-agent decomposition — the platform's core promise — only works one hop
  deep, and any dependency between specialists deadlocks. In practice, work must either go
  through the orchestrator with everything a single agent needs inlined, or fail.
- **Suggested fix:** an agent→agent handoff/ask primitive inside a task (or worker-mediated
  sub-task with resumption), and documentation steering task creation to the orchestrator.

### 4.9 Runtime: mid-task tool availability flaps; ambiguous tool namespaces

- **Observed:** (a) integration tools present early in a run were reported "not available"
  later in the *same* run, sending agents into workarounds. (b) A generic tool family (e.g. a
  generic `crm.*` set) appears alongside the configured plugin's tools and demands its own
  "key connection" even though an active, working integration of that kind exists — agents
  pick the wrong namespace and stall.
- **Impact:** intermittent tool loss is the single biggest source of agent improvisation
  (wrong data sources, invented fallbacks); the duplicate namespace wastes runs on a dead end.
- **Suggested fix:** stable tool inventory for the lifetime of a run; hide generic toolsets
  when a configured plugin of the same category is active (or alias them to it).

### 4.10 Runtime: integration tools cache connection config until it goes stale

- **Observed:** a messaging integration's send tool kept using a cached provider endpoint id
  and failed with the provider's 404 — while the same credentials, used directly against the
  provider's API with the id re-fetched at call time, worked immediately.
- **Impact:** sends fail platform-wide despite a healthy provider account; nothing in the
  task surfaces *why*.
- **Suggested fix:** re-resolve provider-side identifiers at call time (or on error, refresh
  once and retry) instead of trusting cached config.

### 4.11 Runtime: persistent workspace leaks stale artifacts across tasks

- **Observed:** files written during earlier tasks/experiments persist in the runtime
  workspace; later agents discovered them and treated them as current inputs (up to asking
  the operator to choose between live data and a stale file).
- **Impact:** old data contaminates new runs — the failure is silent and looks like a
  reasonable agent decision.
- **Suggested fix:** task-scoped (or at least clearly namespaced + timestamped) workspaces;
  never present a previous task's files as ambient context.

### 4.12 Send-type tools: "accepted" is not "delivered", and there is no status readback

- **Observed:** a message send returns the provider's "accepted" + message id; actual
  delivery can still fail downstream (provider-side filtering, etc.). Delivery receipts go to
  provider webhooks that the platform holds — nothing is exposed to the SDK/API or the task.
- **Impact:** pipelines report success for messages that never arrived; no way to audit.
- **Suggested fix:** surface per-message delivery status (webhook ingestion → queryable
  status on the send record, or at minimum in task logs).

### 4.13 Observability: no step-level progress for a running task

- **Observed:** while a task runs, `result` is empty and only coarse lifecycle events exist
  (§4.2). The agent's actual activity (tool calls, intermediate output) is invisible until
  the task pauses or ends.
- **Impact:** operators cannot tell a working task from a stuck one; debugging happens
  post-mortem.
- **Suggested fix:** stream (or append to `logs`) step-level events — even just tool-call
  names + timestamps would change operability.

## 5. Summary table — blocker per phase

| Phase | Blocker | Ref | Owner |
|---|---|---|---|
| Create task | direct-to-specialist bypasses orchestration silently | §4.8 | runtime/docs |
| Agent works | model substituted silently under `claude_max` | §2 | runtime |
| Agent works | malformed tool-call JSON on some models | §2 | runtime |
| Agent works | tools flap mid-run; ambiguous namespaces | §4.9 | runtime |
| Agent works | stale integration row shadows the valid one | §4.3, §4.4 | backend |
| Agent works | stale workspace artifacts pollute runs | §4.11 | runtime |
| Delegation | specialists can't reach teammates; routed tasks deadlock | §4.8 | runtime |
| HITL gate | agent ends `done` with open questions — gate bypassed | §4.7 | runtime |
| HITL gate | SDK `approve()` 422 | §4.1 | **fixed here** |
| HITL gate | dashboard has no answer UI | §4.5 | dashboard |
| HITL gate | `waiting_blocked` unrecoverable | §4.6 | backend |
| Send | cached provider config → provider 404 | §4.10 | runtime |
| Send | no delivery-status readback | §4.12 | backend |
| Observe | SDK drops `logs` | §4.2 | **fixed here** |
| Observe | no step-level events | §4.13 | backend/runtime |

## 6. General note on mitigations

We kept a production workflow running against all of the above by, in general terms: creating
tasks against the orchestrator agent with fully self-contained specifications, doing
deterministic pre-processing client-side before task creation, and answering gates through
the API directly. All of that is workaround, not design — each item above has a clean
platform-side fix, and we're happy to provide reproduction details for any of them.

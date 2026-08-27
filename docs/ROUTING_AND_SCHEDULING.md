# How work moves between agents

Three things can start a task, and they are not interchangeable:

| | what starts it | the task's `source` |
|---|---|---|
| **You** | `client.tasks.create(...)` | `api` |
| **An edge** | an upstream agent's output | `routing` |
| **A schedule** | a cron expression coming due | `scheduler` |

Most of this page is about the second one, because edges have a default that
is easy to miss and behaviour that is easy to assume.

---

## Edges route on a *mention* unless you say otherwise

An edge created without `condition_expr` does **not** fire on every upstream
result. The server's default condition is `"mention"`, and it fires the edge
only if the upstream agent's output text contains the **name of the target
agent**, case-insensitively.

```python
tester = client.agents.create(workforce_id=wf.id, name="Tester", role="qa", ...)

client.workforces.edges.create(
    workforce_id=wf.id,
    source_agent_id=reviewer.id,
    target_agent_id=tester.id,
)   # condition_expr defaults to "mention"
```

That edge fires when the Reviewer writes something containing `"Tester"` — and
stays silent otherwise. It is the right default for a **supervisor**: a lead
agent names the specialist it is delegating to, and only that one edge fires.
It is the wrong default if you expected a pipe, and nothing reports an edge
that did not fire.

The conditions the server understands:

| `condition_expr` | fires when |
|---|---|
| unset / `"mention"` | the output contains the target agent's name |
| `"always"` | every time the source task completes |
| `"contains:<word>"` | the output contains `<word>` |
| `"signal:<NAME>"` | the output contains `[NAME]` — e.g. `signal:DONE` |
| anything else | **every time** — see below |

> **An expression the server does not recognise fires the edge.** The evaluator
> matches `always`, `contains:` and `signal:`, and returns true for everything
> it does not understand. A typo in a keyword prefix — `contain:reject`,
> `signal DONE` — therefore turns a narrow condition into an unconditional one,
> silently and in the permissive direction. There is no value meaning "never":
> to stop an edge firing, delete it.

So if you want an unconditional hand-off, ask for one:

```python
client.workforces.edges.create(
    workforce_id=wf.id,
    source_agent_id=reviewer.id,
    target_agent_id=tester.id,
    condition_expr="always",
)
```

The workforce templates shipped in [`templates/`](../templates) are all the
supervisor shape — one lead, edges out to specialists, edges back — and they
rely on this default rather than setting a condition.

## Routing does not cascade

A task created by an edge has `source="routing"`, and **a routed task does not
route onward.** This is deliberate: it is what stops `A → B → A` from looping
forever.

The consequence is worth stating plainly, because the graph does not look like
this:

```
A ──always──▶ B ──always──▶ C
             ✓             ✗ C is never created
```

`B` runs. `C` is never reached, no matter what conditions the second edge
carries. **An edge graph is one hop deep from whatever you submitted.** It
delegates; it does not pipeline.

## There is no fan-in

Every edge that fires creates **its own** task. Two edges into the same agent
produce two tasks, not one task with two inputs — there is no join and no wait.

```
architect ──▶ pricing
reviewer  ──▶ pricing      # two pricing tasks, not one with both results
```

## A routed hand-off is truncated

The downstream task's description is built from the upstream result, cut to the
first **2,000 characters**. That is ample for "here is what I decided" and not
enough for a large artefact. If the next agent needs the whole thing, put it
somewhere it can read — a file, a knowledge base — and let the hand-off carry
the pointer.

## Running stages in sequence

Because of the three points above, a multi-stage pipeline is sequenced by the
caller: create a task, wait for it, create the next.

```python
def run_stage(agent_id: str, title: str, description: str) -> str:
    task = client.tasks.create(
        workforce_id=wf.id, title=title,
        description=description, agent_id=agent_id,
    )
    done = client.tasks.wait_for_completion(task.id, timeout=1800)
    if done.status != "done":
        raise RuntimeError(f"{title}: {done.status} — {done.error}")
    return done.result or ""

analysis = run_stage(analyst.id,  "Analyse",  "…")
review   = run_stage(reviewer.id, "Review",   analysis)
draft    = run_stage(architect.id,"Draft",    review)
```

Keep the edges anyway if the shape is worth showing — the dashboard renders
them — but do not rely on them to carry the work.

---

## Schedules: running an agent on a cron

A **schedule** binds a cron expression to one agent. The backend's scheduler
loop wakes on an interval, finds every enabled schedule whose `next_run_at` has
passed, and submits a task for it with `source="scheduler"`.

```python
schedule = client.schedules.create(
    workforce_id=wf.id,
    agent_id=analyst.id,
    title="Morning scan",
    cron_expr="0 7 * * *",          # five fields, evaluated in `timezone`
    description="Check overnight submissions and summarise what changed.",
    timezone="UTC",
)
print(schedule.next_run_at)          # server-computed; not settable
```

`title` and `description` become the title and description of **every task the
schedule submits**, so `description` is where the recurring instruction goes.

```python
client.schedules.list(wf.id)          # every schedule, enabled or not
client.schedules.pause(schedule.id)   # stop firing, keep the definition
client.schedules.resume(schedule.id)
client.schedules.update(schedule.id, cron_expr="30 6 * * *")
client.schedules.delete(schedule.id)
```

Two things to know:

- **A schedule needs an `agent_id`.** It is a binding between a cron and an
  agent, so there is no such thing as a schedule that fires "the workforce".
- **The task it creates is a normal task**, and its `source` is `scheduler`.
  It is not a routed task, so its output *can* fire outgoing edges — subject to
  everything above.

To find what a schedule has produced, list the workforce's tasks and match on
the schedule id the scheduler records:

```python
runs = [t for t in client.tasks.list(wf.id)
        if t.metadata_json.get("schedule_id") == schedule.id]
```

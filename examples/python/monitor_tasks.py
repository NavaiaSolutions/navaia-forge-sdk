"""
NavaiaForge SDK — Monitor Tasks and Token Usage

Demonstrates listing tasks, checking statuses, and querying
observability metrics for a workforce.
"""

from navaia_forge import NavaiaForgeClient

client = NavaiaForgeClient(
    base_url="https://api.navaia.com",
    api_key="nf_your_api_key",
)

WORKFORCE_ID = "wf_your_workforce_id"

# ── 1. List all tasks ──────────────────────────────────────

all_tasks = client.tasks.list(WORKFORCE_ID)
print(f"Total tasks: {len(all_tasks)}\n")

for task in all_tasks:
    status_icon = {
        "done": "[OK]",
        "in_progress": "[..]",
        "pending": "[--]",
        "failed": "[!!]",
        "rejected": "[XX]",
    }.get(task.status, "[??]")

    print(f"  {status_icon} {task.title}")
    print(f"       ID: {task.id}")
    print(f"       Status: {task.status}")
    print(f"       Created: {task.created_at}")
    if task.completed_at:
        print(f"       Completed: {task.completed_at}")
    print()

# ── 2. Filter by status ───────────────────────────────────

in_progress = client.tasks.list(WORKFORCE_ID, status="in_progress")
failed = client.tasks.list(WORKFORCE_ID, status="failed")
print(f"In progress: {len(in_progress)}")
print(f"Failed: {len(failed)}")

# ── 3. Inspect a specific task ─────────────────────────────

if all_tasks:
    latest = all_tasks[0]
    detail = client.tasks.get(latest.id)
    print(f"\nLatest task detail:")
    print(f"  Title:       {detail.title}")
    print(f"  Description: {detail.description}")
    print(f"  Status:      {detail.status}")
    print(f"  Agent:       {detail.agent_id or 'unassigned'}")
    print(f"  Priority:    {detail.priority}")
    if detail.result:
        print(f"  Result:      {detail.result[:200]}...")
    if detail.error:
        print(f"  Error:       {detail.error}")

# ── 4. Observability — metrics summary ─────────────────────

metrics = client.observability.summary(WORKFORCE_ID)
print(f"\nMetrics Summary:")
print(f"  Total tasks:       {metrics['total_tasks']}")
print(f"  Completed:         {metrics['completed_tasks']}")
print(f"  Failed:            {metrics['failed_tasks']}")
print(f"  Active agents:     {metrics['active_agents']}")
print(f"  Tokens today:      {metrics['total_tokens_today']:,}")
print(f"  Cost today:        ${metrics['cost_today']:.4f}")

# ── 5. Cost breakdown ─────────────────────────────────────
#
# `observability.summary` above returns the raw dashboard payload as a dict, on
# purpose — its shape is free to evolve. `observability.cost` is the typed one.

costs = client.observability.cost(WORKFORCE_ID, days=7)
print(f"\nCost (last {costs.period_days} days)")
print(f"  Total tokens:  {costs.total_tokens:,}")
print(f"  Total cost:    ${costs.total_cost_usd:.4f}")

for agent in costs.by_agent:
    print(f"    {agent.agent_name or agent.agent_id}: "
          f"{agent.total_tokens:,} tokens, ${agent.cost_usd:.4f}, "
          f"{agent.call_count} call(s)")
for model in costs.by_model:
    print(f"    {model.model}: {model.total_tokens:,} tokens, "
          f"${model.cost_usd:.4f}")

# ── 6. Re-run failed tasks ────────────────────────────────
#
# There is no `tasks.retry`. The backend retries a task of its own accord after
# a transient failure; a task that has come to rest in `failed` has used those
# attempts up. To run the work again, submit it again.

if failed:
    print(f"\nRe-submitting {len(failed)} failed task(s)...")
    for task in failed:
        again = client.tasks.create(
            workforce_id=WORKFORCE_ID,
            title=task.title,
            description=task.description,
            agent_id=task.agent_id,
        )
        print(f"  Re-submitted: {again.title} -> {again.status}")

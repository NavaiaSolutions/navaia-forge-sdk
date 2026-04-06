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
    }.get(task["status"], "[??]")

    print(f"  {status_icon} {task['title']}")
    print(f"       ID: {task['id']}")
    print(f"       Status: {task['status']}")
    print(f"       Created: {task['created_at']}")
    if task.get("completed_at"):
        print(f"       Completed: {task['completed_at']}")
    print()

# ── 2. Filter by status ───────────────────────────────────

in_progress = client.tasks.list(WORKFORCE_ID, status="in_progress")
failed = client.tasks.list(WORKFORCE_ID, status="failed")
print(f"In progress: {len(in_progress)}")
print(f"Failed: {len(failed)}")

# ── 3. Inspect a specific task ─────────────────────────────

if all_tasks:
    latest = all_tasks[0]
    detail = client.tasks.get(latest["id"])
    print(f"\nLatest task detail:")
    print(f"  Title:       {detail['title']}")
    print(f"  Description: {detail['description']}")
    print(f"  Status:      {detail['status']}")
    print(f"  Agent:       {detail.get('agent_id', 'unassigned')}")
    print(f"  Priority:    {detail['priority']}")
    if detail.get("result"):
        print(f"  Result:      {detail['result'][:200]}...")
    if detail.get("error"):
        print(f"  Error:       {detail['error']}")

# ── 4. Observability — metrics summary ─────────────────────

metrics = client.observability.summary(WORKFORCE_ID)
print(f"\nMetrics Summary:")
print(f"  Total tasks:       {metrics['total_tasks']}")
print(f"  Completed:         {metrics['completed_tasks']}")
print(f"  Failed:            {metrics['failed_tasks']}")
print(f"  Active agents:     {metrics['active_agents']}")
print(f"  Tokens today:      {metrics['total_tokens_today']:,}")
print(f"  Cost today:        ${metrics['cost_today']:.4f}")

# ── 5. Token usage breakdown ──────────────────────────────

token_history = client.observability.token_usage(WORKFORCE_ID, days=7)
print(f"\nToken usage (last 7 days): {len(token_history)} records")

total_input = sum(r["input_tokens"] for r in token_history)
total_output = sum(r["output_tokens"] for r in token_history)
total_cost = sum(r["cost_weighted"] for r in token_history)

print(f"  Input tokens:  {total_input:,}")
print(f"  Output tokens: {total_output:,}")
print(f"  Total cost:    ${total_cost:.4f}")

# ── 6. Retry failed tasks ─────────────────────────────────

if failed:
    print(f"\nRetrying {len(failed)} failed task(s)...")
    for task in failed:
        retried = client.tasks.retry(task["id"])
        print(f"  Retried: {retried['title']} -> {retried['status']}")

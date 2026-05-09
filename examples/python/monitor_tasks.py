"""
NavaiaForge SDK — Monitor Tasks and Cost

Demonstrates listing tasks, checking statuses, and querying
observability metrics for a workforce.

Run:
    export NAVAIA_FORGE_BASE_URL="http://localhost:8000"
    export NAVAIA_FORGE_API_KEY="nf_..."
    export NAVAIA_FORGE_WORKFORCE_ID="wf_..."
    python examples/python/monitor_tasks.py
"""

from __future__ import annotations

import os
import sys

from navaia_forge import NavaiaForgeClient

_STATUS_ICONS: dict[str, str] = {
    "done": "[OK]",
    "in_progress": "[..]",
    "pending": "[--]",
    "failed": "[!!]",
    "rejected": "[XX]",
    "blocked": "[##]",
    "waiting": "[~~]",
}


def main() -> None:
    workforce_id = os.environ.get("NAVAIA_FORGE_WORKFORCE_ID")
    if not workforce_id:
        sys.stderr.write("Set NAVAIA_FORGE_WORKFORCE_ID before running.\n")
        sys.exit(1)

    client = NavaiaForgeClient(
        base_url=os.environ.get("NAVAIA_FORGE_BASE_URL", "http://localhost:8000"),
        api_key=os.environ.get("NAVAIA_FORGE_API_KEY", ""),
    )

    # ── 1. List all tasks ──────────────────────────────────────

    all_tasks = client.tasks.list(workforce_id)
    print(f"Total tasks: {len(all_tasks)}\n")

    for task in all_tasks:
        icon = _STATUS_ICONS.get(task.status, "[??]")
        print(f"  {icon} {task.title}")
        print(f"       ID: {task.id}")
        print(f"       Status: {task.status}")
        print(f"       Created: {task.created_at}")
        if task.completed_at:
            print(f"       Completed: {task.completed_at}")
        print()

    # ── 2. Filter by status ───────────────────────────────────

    in_progress = client.tasks.list(workforce_id, status="in_progress")
    failed = client.tasks.list(workforce_id, status="failed")
    print(f"In progress: {len(in_progress)}")
    print(f"Failed: {len(failed)}")

    # ── 3. Inspect a specific task ─────────────────────────────

    if all_tasks:
        latest = all_tasks[0]
        detail = client.tasks.get(latest.id)
        print("\nLatest task detail:")
        print(f"  Title:       {detail.title}")
        print(f"  Description: {detail.description}")
        print(f"  Status:      {detail.status}")
        print(f"  Agent:       {detail.agent_id or 'unassigned'}")
        print(f"  Priority:    {detail.priority}")
        if detail.result:
            print(f"  Result:      {detail.result[:200]}...")
        if detail.error:
            print(f"  Error:       {detail.error}")

    # ── 4. Observability — metrics summary (raw dict payload) ──

    metrics = client.observability.summary(workforce_id)
    print("\nMetrics Summary:")
    print(f"  Total tasks:       {metrics.get('total_tasks', 0)}")
    print(f"  Completed:         {metrics.get('completed_tasks', 0)}")
    print(f"  Failed:            {metrics.get('failed_tasks', 0)}")
    print(f"  Active agents:     {metrics.get('active_agents', 0)}")
    print(f"  Tokens today:      {metrics.get('total_tokens_today', 0):,}")
    print(f"  Cost today:        ${metrics.get('cost_today', 0):.4f}")

    # ── 5. Cost breakdown over the last 7 days ────────────────

    cost = client.observability.cost(workforce_id, days=7)
    print(f"\nCost (last {cost.period_days} days):")
    print(f"  Total tokens:    {cost.total_tokens:,}")
    print(f"  Weighted tokens: {cost.total_weighted_tokens:,}")
    print(f"  Total cost:      ${cost.total_cost_usd:.4f}")

    if cost.by_model:
        print("\n  By model:")
        for row in cost.by_model:
            print(
                f"    {row.model:<20} "
                f"tokens={row.total_tokens:>10,}  "
                f"cost=${row.cost_usd:.4f}"
            )

    # ── 6. Retry failed tasks ─────────────────────────────────

    if failed:
        print(f"\nRetrying {len(failed)} failed task(s)...")
        for task in failed:
            retried = client.tasks.retry(task.id)
            print(f"  Retried: {retried.title} -> {retried.status}")


if __name__ == "__main__":
    main()

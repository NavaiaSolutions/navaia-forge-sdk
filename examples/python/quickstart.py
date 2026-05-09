"""
NavaiaForge SDK — Quickstart Example

Demonstrates creating a workforce, adding an agent, submitting a task,
and waiting for the result.

Run:
    export NAVAIA_FORGE_BASE_URL="http://localhost:8000"
    export NAVAIA_FORGE_API_KEY="nf_..."
    python examples/python/quickstart.py
"""

from __future__ import annotations

import os

from navaia_forge import NavaiaForgeClient


def main() -> None:
    client = NavaiaForgeClient(
        base_url=os.environ.get("NAVAIA_FORGE_BASE_URL", "http://localhost:8000"),
        api_key=os.environ.get("NAVAIA_FORGE_API_KEY", ""),
    )

    # Create a workforce
    workforce = client.workforces.create(
        name="My First Workforce",
        description="Testing NavaiaForge",
    )
    print(f"Workforce created: {workforce.id}")

    # Add an agent
    agent = client.agents.create(
        workforce_id=workforce.id,
        name="Researcher",
        role="research",
        instructions="Find and summarize information on any given topic.",
        model_provider="anthropic",
        model_name="sonnet",
    )
    print(f"Agent created: {agent.id}")

    # Submit a task
    task = client.tasks.create(
        workforce_id=workforce.id,
        title="Research AI trends in 2025",
        description="Provide a comprehensive summary of the top AI trends.",
        agent_id=agent.id,
    )
    print(f"Task submitted: {task.id}")

    # Wait for completion
    result = client.tasks.wait_for_completion(task.id, timeout=300)
    print(f"Status: {result.status}")
    print(f"Result: {result.result}")


if __name__ == "__main__":
    main()

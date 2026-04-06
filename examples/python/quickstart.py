"""
NavaiaForge SDK — Quickstart Example

Demonstrates creating a workforce, adding an agent, submitting a task,
and waiting for the result.
"""

from navaia_forge import NavaiaForgeClient

client = NavaiaForgeClient(
    base_url="https://api.navaia.com",
    api_key="nf_your_api_key",
)

# Create a workforce
workforce = client.workforces.create(
    name="My First Workforce",
    description="Testing NavaiaForge",
)
print(f"Workforce created: {workforce['id']}")

# Add an agent
agent = client.agents.create(
    workforce_id=workforce["id"],
    name="Researcher",
    role="research",
    instructions="Find and summarize information on any given topic.",
    model_provider="anthropic",
    model_name="sonnet",
)
print(f"Agent created: {agent['id']}")

# Submit a task
task = client.tasks.create(
    workforce_id=workforce["id"],
    title="Research AI trends in 2025",
    description="Provide a comprehensive summary of the top AI trends.",
    agent_id=agent["id"],
)
print(f"Task submitted: {task['id']}")

# Wait for completion
result = client.tasks.wait_for_completion(task["id"], timeout=300)
print(f"Status: {result['status']}")
print(f"Result: {result['result']}")

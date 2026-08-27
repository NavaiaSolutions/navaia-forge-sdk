"""
NavaiaForge SDK — Quickstart Example

Creates a workforce, adds an agent, submits a task, and waits for the result.

Every resource method returns a **typed model**, not a dict, so read fields
with attribute access: `workforce.id`, not `workforce["id"]`.
"""

from navaia_forge import NavaiaForgeClient

client = NavaiaForgeClient(
    base_url="http://localhost:8001",
    api_key="nf_your_api_key",
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

# Submit a task. Naming the agent sends it straight there; leave `agent_id` off
# to let the workforce decide.
task = client.tasks.create(
    workforce_id=workforce.id,
    title="Research AI trends",
    description="Provide a comprehensive summary of the top AI trends.",
    agent_id=agent.id,
)
print(f"Task submitted: {task.id}")

# Wait for completion. `timeout` is in seconds; a long task needs a bigger one.
result = client.tasks.wait_for_completion(task.id, timeout=300)
print(f"Status: {result.status}")
print(f"Result: {result.result}")

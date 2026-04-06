"""
NavaiaForge SDK — Create a Multi-Agent Workforce

Demonstrates building a workforce with multiple specialized agents
connected by edges to form an automated pipeline.
"""

from navaia_forge import NavaiaForgeClient

client = NavaiaForgeClient(
    base_url="https://api.navaia.com",
    api_key="nf_your_api_key",
)

# ── 1. Create the workforce ────────────────────────────────

workforce = client.workforces.create(
    name="Content Pipeline",
    description="Research, write, and review content automatically.",
    runtime_mode="claude_max",
)
print(f"Workforce: {workforce['id']}")

# ── 2. Add specialized agents ──────────────────────────────

researcher = client.agents.create(
    workforce_id=workforce["id"],
    name="Researcher",
    role="research",
    instructions=(
        "Search the web and compile detailed notes on the assigned topic. "
        "Cite sources and highlight key statistics."
    ),
    model_provider="anthropic",
    model_name="sonnet",
    tools=["web_search"],
    position_x=100,
    position_y=200,
)

writer = client.agents.create(
    workforce_id=workforce["id"],
    name="Writer",
    role="writing",
    instructions=(
        "Using the research notes provided, write a polished article. "
        "Use clear headings, concise paragraphs, and an engaging tone."
    ),
    model_provider="anthropic",
    model_name="sonnet",
    position_x=400,
    position_y=200,
)

reviewer = client.agents.create(
    workforce_id=workforce["id"],
    name="Reviewer",
    role="review",
    instructions=(
        "Review the article for factual accuracy, grammar, and style. "
        "Provide specific suggestions and a quality score from 1-10."
    ),
    model_provider="anthropic",
    model_name="sonnet",
    position_x=700,
    position_y=200,
)

print(f"Agents created: {researcher['name']}, {writer['name']}, {reviewer['name']}")

# ── 3. Connect agents with edges ───────────────────────────
# Edges define the flow: Researcher -> Writer -> Reviewer

workforce_full = client.workforces.get_full(workforce["id"])
print(f"Workforce has {len(workforce_full.get('agents', []))} agents")

# NOTE: Edge creation is typically done via the workforce update API
# or through the visual canvas in the NavaiaForge UI.

client.workforces.update(
    workforce["id"],
    config_json={
        "edges": [
            {
                "source_agent_id": researcher["id"],
                "target_agent_id": writer["id"],
                "approval_mode": "auto_run",
                "label": "Research complete",
            },
            {
                "source_agent_id": writer["id"],
                "target_agent_id": reviewer["id"],
                "approval_mode": "auto_run",
                "label": "Draft ready",
            },
        ],
    },
)

# ── 4. Submit a task to kick off the pipeline ──────────────

task = client.tasks.create(
    workforce_id=workforce["id"],
    title="Write an article about quantum computing breakthroughs",
    description=(
        "Research the latest quantum computing advances in 2025, "
        "write a 1500-word article, and review it for publication."
    ),
    agent_id=researcher["id"],
    priority="high",
)

print(f"Pipeline started — task {task['id']}")
print(f"Track progress at: https://app.navaia.com/workforces/{workforce['id']}")

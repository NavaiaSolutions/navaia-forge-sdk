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
print(f"Workforce: {workforce.id}")

# ── 2. Add specialized agents ──────────────────────────────

researcher = client.agents.create(
    workforce_id=workforce.id,
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
    workforce_id=workforce.id,
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
    workforce_id=workforce.id,
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

print(f"Agents created: {researcher.name}, {writer.name}, {reviewer.name}")

# ── 3. Connect agents with edges ───────────────────────────
# Edges are their own resource. They are NOT part of `config_json` — writing
# them there creates nothing.

client.workforces.edges.create(
    workforce_id=workforce.id,
    source_agent_id=researcher.id,
    target_agent_id=writer.id,
    approval_mode="auto_run",
    label="Research complete",
    condition_expr="always",
)
client.workforces.edges.create(
    workforce_id=workforce.id,
    source_agent_id=writer.id,
    target_agent_id=reviewer.id,
    approval_mode="auto_run",
    label="Draft ready",
    condition_expr="always",
)

# `condition_expr` is set deliberately. Left unset it defaults to "mention",
# which fires an edge only when the upstream output contains the target agent's
# NAME — right for a supervisor delegating by name, wrong for a hand-off.

workforce_full = client.workforces.get_full(workforce.id)
print(f"Workforce has {len(workforce_full.agents)} agents "
      f"and {len(workforce_full.edges)} edges")

# ── 4. Run the three stages ────────────────────────────────
#
# Edges delegate ONE hop: a task created by routing does not route onward, so
# submitting to the Researcher runs the Writer and stops — the Reviewer is
# never reached. Sequence the stages yourself when you need all three.
# See docs/ROUTING_AND_SCHEDULING.md.

def run_stage(agent_id: str, title: str, description: str) -> str:
    task = client.tasks.create(
        workforce_id=workforce.id,
        title=title,
        description=description,
        agent_id=agent_id,
        priority="high",
    )
    print(f"  {title} — task {task.id}")
    done = client.tasks.wait_for_completion(task.id, timeout=1800)
    if done.status != "done":
        raise RuntimeError(f"{title} ended {done.status}: {done.error}")
    return done.result or ""

topic = "the latest quantum computing advances"
notes = run_stage(researcher.id, "Research", f"Compile detailed notes on {topic}.")
draft = run_stage(writer.id, "Write", f"Write a 1500-word article from these notes:\n\n{notes}")
review = run_stage(reviewer.id, "Review", f"Review this article for publication:\n\n{draft}")

print(f"\nDone. Review:\n{review[:500]}")

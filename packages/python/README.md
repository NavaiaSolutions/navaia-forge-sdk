# NavaiaForge Python SDK

Official Python client for the [NavaiaForge](https://navaia.com) AI workforce platform — a typed, real-time client for building **multi-agent AI workforces** that work like teams.

Use it **standalone** (scripts, services, CI, notebooks) or **alongside the NavaiaForge dashboard**. Both speak to the same backend, so anything created in code shows up in the UI and vice versa.

## Why a workforce, not just an agent?

A single LLM call solves a single prompt; real work rarely is. NavaiaForge models work the way teams do:

- **Many specialized agents** with their own roles, instructions, and models — not one generalist.
- **Edges** route work between them (reviewer → tester → deployer).
- **Shared knowledge bases** ground every agent in the same facts via RAG.
- **Shared tools** (HTTP, MCP, code executors, plugins) give the team hands.
- **One coordinator** — submit a task to the workforce, not to a specific agent.

The SDK exposes every primitive directly.

## Installation

```bash
pip install navaia-forge
```

## Quickstart

```python
from navaia_forge import NavaiaForgeClient

client = NavaiaForgeClient(base_url="http://localhost:8000", api_key="nf_...")

# Build the team
wf = client.workforces.create(name="Code Review Team")
reviewer = client.agents.create(workforce_id=wf.id, name="Reviewer", role="review",
                                instructions="Review PRs for correctness and security.",
                                model_provider="anthropic", model_name="sonnet")
tester   = client.agents.create(workforce_id=wf.id, name="Tester", role="qa",
                                instructions="Generate and run tests for approved diffs.",
                                model_provider="anthropic", model_name="sonnet")

# Wire reviewer → tester
client.workforces.create_edge(workforce_id=wf.id,
                              source_agent_id=reviewer.id,
                              target_agent_id=tester.id)

# Hand work to the team
task  = client.tasks.create(workforce_id=wf.id, title="Review PR #482 and add tests")
final = client.tasks.wait_for_completion(task.id)
print(final.status, final.result)
```

All resource methods return typed [Pydantic v2](https://docs.pydantic.dev/) models. Errors raise `navaia_forge.NavaiaForgeError` (or a subclass: `NotFoundError`, `RateLimitError`, `ValidationError`, `AuthenticationError`, `PermissionError`, `ServerError`, `TimeoutError`).

## Real-time events

```python
from navaia_forge import NavaiaForgeWs, HttpConfig

ws = NavaiaForgeWs(HttpConfig(base_url="http://localhost:8000", api_key="nf_..."))
ws.on("task:status",  lambda e: print("task:",  e["task_id"], e["status"]))
ws.on("agent:status", lambda e: print("agent:", e["agent_id"], e["status"]))
ws.on("chat:message", lambda e: print(e["role"], e["content"]))
ws.connect()
ws.run_forever()
```

Channels: `task:status`, `agent:status`, `chat:message`, `system:*`.

## What you can do

| Namespace | What it does | Why you'd use it |
|---|---|---|
| `client.workforces` | CRUD; manage edges; link tools / knowledge bases | Define the team and how work flows through it |
| `client.agents` | CRUD; `list_featured`, `clone`, `export`; attach/detach to workforces | Compose specialists with their own models and instructions |
| `client.tasks` | `create`, `approve`, `reject`, `retry`, logs, `wait_for_completion` | Hand work to the team, sync or async |
| `client.conversations` | Open chats, send messages targeted at agents | Build chat UIs / interactive assistants |
| `client.knowledge` | Knowledge bases, document upload, semantic `search`, `featured`, `download` | Ground agents in your data via RAG |
| `client.templates` | Workforce templates + `templates.agents` for agent templates | Don't rebuild the same team twice |
| `client.tools` | Full CRUD, `featured`, attach/detach to workforces | Give the team hands (HTTP, MCP, code-exec, custom) |
| `client.integrations` | `list`, `list_plugins`, CRUD | Connect Slack / GitHub / Linear / other plugins |
| `client.setup` | `options`, `validate`, `complete` | First-run onboarding / provider configuration |
| `client.observability` | `summary`, `cost`, `agent_metrics`, `agent_evaluations`, `log_token_usage` | See what the team is doing and what it costs |
| `client.auth` | `me`, `register`, `login`, `refresh`, `create_key`, `validate`, OAuth URL helpers | Build your own UI on top of NavaiaForge |

## Standalone or with the UI

- **Standalone:** the SDK is sufficient on its own — no dashboard required. Drive everything from Python: scripts, services, Airflow / Prefect tasks, Jupyter, custom CLIs, internal tools.
- **Alongside the dashboard:** anything you create programmatically appears in the NavaiaForge UI immediately, and anything created in the UI is reachable from `client.*`. Two views over one backend.

## Development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest --cov=navaia_forge
ruff check navaia_forge tests
```

## License

[MIT](./LICENSE) © NavaiaSolutions

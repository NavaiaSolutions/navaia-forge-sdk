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

## ⚠️ Run the backend first

**This SDK is a client.** It needs a NavaiaForge backend to talk to. There's **no hosted service yet** — today the only way to get a backend is to **run it yourself with Docker**. That sounds like a chore; it's actually the point:

- **Your data stays on your infrastructure** — prompts, agent outputs, KBs, conversations.
- **No per-token markup, no rate limits** — you pay your LLM provider directly.
- **Air-gapped friendly** — works offline, on-prem, in regulated environments.
- **No vendor lock-in** — the image and database are yours.

Your options: run it on your **laptop** (dev / learning), on your **own VM or cluster** (production), or **air-gapped on-prem** (compliance). Same image, same SDK code, just a different `base_url`.

```bash
curl -fLO https://raw.githubusercontent.com/NavaiaSolutions/NavaiaForge/main/docker-compose.dist.yml
# create .env with your secrets (see .env.example), then:
docker compose -f docker-compose.dist.yml up -d
# → API at http://localhost:8001
```

Always point `base_url` at your local backend (e.g. `http://localhost:8001`). Full walkthrough: [`SETUP.md`](https://github.com/NavaiaSolutions/navaia-forge-sdk/blob/main/SETUP.md).

## Installation

```bash
pip install navaia-forge
```

## Quickstart

```python
from navaia_forge import NavaiaForgeClient

# Point at the backend you started with `docker compose up`.
client = NavaiaForgeClient(base_url="http://localhost:8001", api_key="nf_...")

# Build the team
wf = client.workforces.create(name="Code Review Team")
reviewer = client.agents.create(workforce_id=wf.id, name="Reviewer", role="review",
                                instructions="Review PRs for correctness and security.",
                                model_provider="anthropic", model_name="sonnet")
tester   = client.agents.create(workforce_id=wf.id, name="Tester", role="qa",
                                instructions="Generate and run tests for approved diffs.",
                                model_provider="anthropic", model_name="sonnet")

# Wire reviewer → tester
client.workforces.edges.create(workforce_id=wf.id,
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

ws = NavaiaForgeWs(HttpConfig(base_url="http://localhost:8001", api_key="nf_..."))
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

## LangGraph integration

Already have a LangGraph workforce? Run it inside Forge with one wrapper — keep your graph code, gain Forge observability and backend access.

```bash
pip install "navaia-forge[langgraph]"
```

```python
from langchain_core.runnables import RunnableConfig

from navaia_forge import NavaiaForgeClient
from navaia_forge.integrations.langgraph import LangGraphWorkforce, get_forge_context

# Annotate `config` as RunnableConfig — modern LangGraph only injects
# the config dict into nodes that explicitly opt in via this type hint.
def search_node(state: dict, config: RunnableConfig) -> dict:
    forge = get_forge_context(config)
    hits = forge.client.knowledge.search(forge.workforce_id, state["query"])
    return {"hits": [h.model_dump() for h in hits.results]}

# Wrap a compiled graph; the wrapper installs the Forge callback and
# injects `ForgeContext` on `RunnableConfig.configurable` for you.
wf = LangGraphWorkforce(
    graph=my_compiled_graph,
    client=NavaiaForgeClient(base_url="http://localhost:8001", api_key="nf_..."),
    workforce_id="wf_existing",
)
result = wf.run({"query": "..."}, task_id="task_123")
```

Token usage from every LLM call lands on the workforce's cost dashboard. See `examples/python/langgraph_workforce.py` for a full end-to-end run.

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

Apache-2.0

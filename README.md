# NavaiaForge SDK

**Build AI workforces that work like a team — from code, from the UI, or both.**

[![npm version](https://img.shields.io/npm/v/navaia-forge)](https://www.npmjs.com/package/navaia-forge)
[![PyPI version](https://img.shields.io/pypi/v/navaia-forge)](https://pypi.org/project/navaia-forge/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)

NavaiaForge is a platform for building **multi-agent AI workforces** — groups of specialized agents that share context, hand off work to each other, draw on shared knowledge, call shared tools, and stream results back to you in real time. This repo contains the official **TypeScript** and **Python** SDKs.

The SDK is a complete client over the same backend that powers the NavaiaForge dashboard. Use it:

- **Standalone** — run everything from code: scripts, services, CI, notebooks, internal tools. No dashboard required.
- **Alongside the UI** — anything you build in code appears in the dashboard immediately, and anything built in the dashboard is reachable from the SDK. Same workforces, same agents, same tasks. Two views over one backend.

---

## You run the backend — that's the point

NavaiaForge has two pieces:

1. **The SDK** (this repo) — a typed HTTP client you `pip install` or `npm install`.
2. **The backend** — a Docker container you run on your machine. It stores workforces, executes agents, holds knowledge bases, and streams events.

**All execution happens on your machine.** You bring your own LLM keys (Anthropic, OpenRouter), you run the container, you own the data. One Docker command to start:

```bash
curl -fLO https://raw.githubusercontent.com/NavaiaSolutions/NavaiaForge/main/docker-compose.dist.yml
# Configure .env — see SETUP.md
docker compose -f docker-compose.dist.yml up -d
```

Your backend is now at `http://localhost:8001`. Point the SDK at it.

### The cloud dashboard is optional

The hosted UI at `fareegi.navaia.sa` is a **display layer** — browse the marketplace, visualise your workforces, share results. No execution happens there. Use `client.sync.push()` to send results to the dashboard when you want to, or skip it entirely and run offline.

```python
# All execution is local
local = NavaiaForgeClient(base_url="http://localhost:8001", api_key="nf_local...")

# Optionally sync results to the cloud dashboard
cloud = NavaiaForgeClient(base_url="https://fareegi.navaia.sa", api_key="nf_cloud...")
local.sync.push(workforce_id, remote=cloud)
```

> **Want managed hosting?** Contact `info@navaia.sa` for a deployment where we run the backend on your behalf.

### Why this is good for you

- **Your data stays on your machine.** Prompts, outputs, knowledge bases — nothing leaves unless you sync it.
- **No per-token markup.** You pay your LLM provider directly. NavaiaForge doesn't sit in the middle.
- **No vendor lock-in.** The Docker image, database, and data are yours.
- **Works offline.** Once pulled, the SDK + local backend are fully self-contained.
- **One command to upgrade.** `docker compose pull && docker compose up -d`.

Full walkthrough: **[`SETUP.md`](./SETUP.md)**.

---

## Why a workforce, not just an agent?

A single LLM call solves a single prompt. Real work is rarely a single prompt. NavaiaForge models work the way teams actually do it:

- **Many specialized agents instead of one generalist.** A reviewer, a tester, a writer, a researcher — each with its own role, instructions, and model.
- **Edges that route work between them.** When the reviewer is done, the result flows to the tester. You define the graph; the workforce executes it.
- **Shared knowledge.** Attach knowledge bases (PDFs, docs, RAG-indexed sources) to a workforce so every agent can ground its answers in the same facts.
- **Shared tools.** Give the team HTTP endpoints, MCP servers, code executors, custom integrations — once, at the workforce level.
- **One coordinator.** Submit a task to the workforce, not to a specific agent. The platform routes, executes, retries, and streams events back.

The SDK exposes every one of those primitives directly.

---

## What the SDK lets you do

### Build the team

```python
wf = client.workforces.create(name="Code Review Team")

reviewer = client.agents.create(
    workforce_id=wf.id,
    name="Reviewer",
    role="review",
    instructions="Review pull requests for correctness, style, and security.",
    model_provider="anthropic", model_name="sonnet",
)
tester = client.agents.create(
    workforce_id=wf.id,
    name="Tester",
    role="qa",
    instructions="Generate and run tests against changes the reviewer approves.",
    model_provider="anthropic", model_name="sonnet",
)

# Wire reviewer → tester so approved diffs flow downstream automatically.
client.workforces.edges.create(
    workforce_id=wf.id,
    source_agent_id=reviewer.id,
    target_agent_id=tester.id,
)
```

### Give the team shared knowledge

```python
kb = client.knowledge.create(name="Product Docs", workforce_id=wf.id)
# Every agent in the workforce can now retrieve from "Product Docs" via RAG.
results = client.knowledge.search(kb.id, query="deployment checklist")
```

### Run a task across the team

```python
task = client.tasks.create(workforce_id=wf.id, title="Review PR #482 and add tests")
final = client.tasks.wait_for_completion(task.id)  # blocks with smart polling
print(final.status, final.result)
```

### Watch it happen in real time

```python
from navaia_forge import NavaiaForgeWs, HttpConfig

ws = NavaiaForgeWs(HttpConfig(base_url="http://localhost:8001", api_key="nf_..."))
ws.on("task:status",   lambda e: print("task:",   e["task_id"], e["status"]))
ws.on("agent:status",  lambda e: print("agent:",  e["agent_id"], e["status"]))
ws.on("chat:message",  lambda e: print(e["role"], e["content"]))
ws.connect()
ws.run_forever()
```

### Skip the boilerplate with templates

```python
result = client.templates.instantiate(template_id="engineering-workforce", name="My Team")
# Pre-built workforces (engineering, QA, generalist) — instantiated and ready to run.
```

### Have a conversation with an agent

```python
conv = client.conversations.create(workforce_id=wf.id)
client.conversations.send_message(conv.id, content="What did the reviewer flag?", agent_id=reviewer.id)
for msg in client.conversations.messages(conv.id):
    print(msg.role, msg.content)
```

### Watch your costs and quality

```python
client.observability.summary(workforce_id=wf.id)                # tokens / spend overview
client.observability.cost(workforce_id=wf.id)                   # cost broken down by model
client.observability.agent_metrics(agent_id=reviewer.id)        # per-agent perf
client.observability.agent_evaluations(agent_id=reviewer.id)    # RL evals
```

### Plug in third-party services

```python
client.integrations.list_plugins()  # browse available plugins (Slack, GitHub, Linear, ...)
client.integrations.create(plugin_name="slack", display_name="Eng Slack", config={...})
```

### Authenticate users in your own UI

```python
pair = client.auth.login(email="alice@acme.com", password="...")
client.auth.create_key("ci-runner")     # mint API keys for headless services
client.auth.google_login_url()           # build OAuth start URLs for your frontend
```

---

## Feature catalog

Every namespace below works the same way in TypeScript (`nf.*`) and Python (`client.*`).

| Namespace | What it does | Why you'd use it |
|---|---|---|
| **workforces** | CRUD workforces; manage edges between agents | Define the team and how work flows through it |
| **agents** | Full CRUD, `export` | Compose specialists with their own roles, models, and instructions |
| **tasks** | Submit, approve, reject, `wait_for_completion` | Hand work to the team and get results — sync or async |
| **conversations** | Open chats with workforces, send messages targeted at specific agents | Build chat UIs, support bots, interactive assistants |
| **knowledge** | Knowledge bases, semantic search | Ground agents in your own data via RAG |
| **templates** | Workforce templates + `templates.agents` for agent templates | Don't rebuild the same team twice; instantiate from a blueprint |
| **marketplace** | Browse published workforces (`list`, `get`) and `install` them into your backend | Run teams others have published — not just your own |
| **integrations** | Manage plugin integrations: list installed, browse `list_plugins`, CRUD | Connect Slack, GitHub, Linear, and other third-party services |
| **observability** | Token-usage summary, cost breakdowns, per-agent metrics, RL evaluations, manual usage logging | See what the team is doing, what it costs, and where it's failing |
| **sync** | Export/import bundles, `push`/`pull` between local and cloud, file round-trip | Sync workforces to the cloud dashboard or between instances |
| **auth** | `me`, register/login/refresh, API-key creation/validation, OAuth helpers | Power your own UI on top of NavaiaForge |
| **WebSocket** (`nf.ws` / `NavaiaForgeWs`) | Real-time streams: task status, agent status, chat messages, system events | React the moment something happens — no polling |

---

## Who it helps

- **Engineers building AI features** — typed client, IDE autocomplete, no need to hand-write HTTP plumbing.
- **Teams running agents in production** — observability, cost tracking, evaluations, and retries are first-class.
- **People building custom UIs on top of NavaiaForge** — auth flows, conversations, and the WebSocket stream let you build a fully custom frontend.
- **Automation owners** — drive everything from CI, schedulers, or your existing services. No browser in the loop.
- **Researchers & power users** — drop into a notebook, spin up a workforce, iterate fast. Then promote to production unchanged.

---

## Installation

### TypeScript / JavaScript

```bash
npm install navaia-forge
```

```ts
import { NavaiaForge } from "navaia-forge";

const nf = new NavaiaForge({
  apiKey: "nf_your_api_key",
  baseUrl: "http://localhost:8001", // your self-hosted backend (see SETUP.md)
});

const workforce = await nf.workforces.create({ name: "Research Team" });
const agent = await nf.agents.create({
  workforce_id: workforce.id,
  name: "Researcher",
  role: "research",
  instructions: "Find and summarize information on any given topic.",
  model_provider: "anthropic",
  model_name: "sonnet",
});
const task = await nf.tasks.create({
  workforce_id: workforce.id,
  agent_id: agent.id,
  title: "Survey 2025 LLM efficiency papers",
});
const result = await nf.tasks.waitForCompletion(task.id);
console.log(result.result);
```

### Python

```bash
pip install navaia-forge
```

```python
from navaia_forge import NavaiaForgeClient

client = NavaiaForgeClient(
    base_url="http://localhost:8001",  # your self-hosted backend (see SETUP.md)
    api_key="nf_your_api_key",
)

workforce = client.workforces.create(name="Research Team")
agent = client.agents.create(
    workforce_id=workforce.id,
    name="Researcher",
    role="research",
    instructions="Find and summarize information on any given topic.",
    model_provider="anthropic", model_name="sonnet",
)
task = client.tasks.create(
    workforce_id=workforce.id,
    agent_id=agent.id,
    title="Survey 2025 LLM efficiency papers",
)
final = client.tasks.wait_for_completion(task.id)
print(final.status, final.result)
```

All Python resource methods return typed [Pydantic v2](https://docs.pydantic.dev/) models. Errors raise `navaia_forge.NavaiaForgeError` (or a subclass: `NotFoundError`, `RateLimitError`, `ValidationError`, `AuthenticationError`, `PermissionError`, `ServerError`, `TimeoutError`).

---

## Templates

Pre-built workforce templates live in [`templates/`](./templates/):

- **Engineering Workforce** — code review, testing, deployment agents
- **Navaia Workforce** — general-purpose multi-agent team
- **QA Workforce** — automated testing and quality assurance

```ts
const result = await nf.templates.instantiate("engineering-workforce", "My Team");
```

---

## Examples

Runnable end-to-end examples in [`examples/`](./examples/):

- [Quickstart (Python)](./examples/python/quickstart.py)
- [Quickstart (TypeScript)](./examples/javascript/quickstart.ts)
- [Multi-Agent Workforce (Python)](./examples/python/create_workforce.py)
- [Multi-Agent Workforce (TypeScript)](./examples/javascript/create-workforce.ts)
- [Task Monitoring (Python)](./examples/python/monitor_tasks.py)
- [Task Monitoring (TypeScript)](./examples/javascript/monitor-tasks.ts)

---

## Documentation

- [Setup Guide](./SETUP.md) — backend, SDK install, framework interop (LangGraph, LangChain, CrewAI, …)
- API Reference — coming soon
- Platform Guide — coming soon
- [Contributing](./CONTRIBUTING.md)

---

## Contributing

We welcome contributions. Please read our [Contributing Guide](./CONTRIBUTING.md) and sign our [Contributor License Agreement](./CLA.md) before submitting a pull request.

---

## License

This project is licensed under the [AGPL-3.0 License](./LICENSE).

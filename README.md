# NavaiaForge SDK

**Build AI workforces that work like a team — from code, from the UI, or both.**

[![npm version](https://img.shields.io/npm/v/@navaia/forge)](https://www.npmjs.com/package/@navaia/forge)
[![PyPI version](https://img.shields.io/pypi/v/navaia-forge)](https://pypi.org/project/navaia-forge/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)

NavaiaForge is a platform for building **multi-agent AI workforces** — groups of specialized agents that share context, hand off work to each other, draw on shared knowledge, call shared tools, and stream results back to you in real time. This repo contains the official **TypeScript** and **Python** SDKs.

The SDK is a complete client over the same backend that powers the NavaiaForge dashboard. Use it:

- **Standalone** — run everything from code: scripts, services, CI, notebooks, internal tools. No dashboard required.
- **Alongside the UI** — anything you build in code appears in the dashboard immediately, and anything built in the dashboard is reachable from the SDK. Same workforces, same agents, same tasks. Two views over one backend.

---

## ⚠️ You run the backend yourself (and that's a feature)

### What's actually going on?

NavaiaForge has two pieces:

1. **The SDK** (this repo) — a small library you `pip install` or `npm install` into your own code. It's just a typed HTTP client.
2. **The backend** — the actual brain. It stores your workforces, runs agents, holds knowledge bases, talks to LLMs, streams events. It's a server.

The SDK can't do anything on its own — it needs a backend to talk to. **Right now there is no hosted NavaiaForge service.** We don't run a server on the internet that you can point your API key at. The only way to get a backend is to **run it yourself**, which takes one Docker command.

> Once it's running, the SDK talks to it the same way it would talk to any hosted service. Your code doesn't change.

### Your options

| Option | What it looks like | Best for |
|---|---|---|
| **Run it on your laptop** | `docker compose up` on your dev machine. Backend at `http://localhost:8001`. | Trying it out, building locally, demos, learning. |
| **Run it on your own server** | Same compose file on a VM (EC2, GCP, your own box) or a Kubernetes cluster. | Production, team use, anything that needs to outlive your laptop. |
| **Air-gapped / on-prem** | Same image, no internet required after install. | Regulated industries (healthcare, finance, defense), strict compliance. |
| **Hosted by Navaia** | Not available yet. When it ships, you'll change one URL — `base_url` — and nothing else. | Future. |

There's no "free tier vs paid tier" you have to pick from a pricing page. You install it, you own it.

### Why this is actually good for you

- **Your data never leaves your infrastructure.** Prompts, agent outputs, knowledge bases, conversations, source code, customer data — all of it sits on a machine you control. Nothing transits a Navaia-owned server.
- **No per-token markup, no rate limits.** You pay your LLM provider directly (Anthropic, OpenAI, your own model). NavaiaForge doesn't sit in the middle taking a cut or throttling you.
- **No vendor lock-in on the runtime.** If we vanish tomorrow, your workforces keep running. The image is yours; the database is yours; the data is yours.
- **It's just Postgres + a container.** Backups, migrations, monitoring, secrets management — use whatever your team already uses. No proprietary console you have to learn.
- **Compliance works the way your security team already wants it to.** SOC2, HIPAA, GDPR data residency, on-prem requirements — none of it is a "talk to sales" conversation, because the data is on your side of the wire by default.
- **It works offline.** Once it's pulled, you can run it on a plane, in a SCIF, in a regional outage. The SDK + your local backend are self-contained.
- **One command to upgrade, one command to roll back.** `docker compose pull && up -d`. If a release breaks something, pin the previous tag and you're back.

### One Docker command

```bash
# 1. Pull the published compose file
curl -fLO https://raw.githubusercontent.com/NavaiaSolutions/NavaiaForge/main/docker-compose.dist.yml

# 2. Configure (license token from licensing@navaia.com)
cat > .env <<'EOF'
NAVAIA_LICENSE=eyJ...your-token...
NAVAIA_LICENSE_ENFORCEMENT=strict
NAVAIA_BACKEND_VERSION=v1.0.0
NAVAIA_FRONTEND_VERSION=v1.0.0
POSTGRES_USER=navaia_forge
POSTGRES_PASSWORD=change-me-please
POSTGRES_DB=navaia_forge
API_PORT=8001
UI_PORT=3030
EOF

# 3. Bring it up
docker compose -f docker-compose.dist.yml up -d
```

Your backend is now at **`http://localhost:8001`** (optional dashboard at `http://localhost:3030`). Point the SDK at that URL — **not** at any `api.navaia.com` host, which doesn't serve traffic.

Full walkthrough (license, upgrades, air-gapped installs, troubleshooting): **[`SETUP.md`](./SETUP.md)**.

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
| **workforces** | CRUD workforces; manage edges between agents; link tools and knowledge bases | Define the team and how work flows through it |
| **agents** | Full CRUD, `export` | Compose specialists with their own roles, models, and instructions |
| **tasks** | Submit, approve, reject, `wait_for_completion` | Hand work to the team and get results — sync or async |
| **conversations** | Open chats with workforces, send messages targeted at specific agents | Build chat UIs, support bots, interactive assistants |
| **knowledge** | Knowledge bases, semantic search | Ground agents in your own data via RAG |
| **templates** | Workforce templates + `templates.agents` for agent templates | Don't rebuild the same team twice; instantiate from a blueprint |
| **marketplace** | Browse published workforces (`list`, `get`) and `install` them into your backend | Run teams others have published — not just your own |
| **integrations** | Manage plugin integrations: list installed, browse `list_plugins`, CRUD | Connect Slack, GitHub, Linear, and other third-party services |
| **observability** | Token-usage summary, cost breakdowns, per-agent metrics, RL evaluations, manual usage logging | See what the team is doing, what it costs, and where it's failing |
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
npm install @navaia/forge
```

```ts
import { NavaiaForge } from "@navaia/forge";

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
- [API Reference](https://docs.navaia.com/api)
- [Platform Guide](https://docs.navaia.com/guide)
- [Contributing](./CONTRIBUTING.md)

---

## Contributing

We welcome contributions. Please read our [Contributing Guide](./CONTRIBUTING.md) and sign our [Contributor License Agreement](./CLA.md) before submitting a pull request.

---

## License

This project is licensed under the [AGPL-3.0 License](./LICENSE).

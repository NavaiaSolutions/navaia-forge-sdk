# NavaiaForge SDK

**Build AI workforces that work like a team — from code, from the UI, or both.**

[![npm version](https://img.shields.io/npm/v/@navaia/forge)](https://www.npmjs.com/package/@navaia/forge)
[![PyPI version](https://img.shields.io/pypi/v/navaia-forge)](https://pypi.org/project/navaia-forge/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

NavaiaForge is a platform for building **multi-agent AI workforces** — groups of specialized agents that share context, hand off work to each other, draw on shared knowledge, call shared tools, and stream results back to you in real time. This repo contains the official **TypeScript** and **Python** SDKs.

The SDK is a complete client over the same backend that powers the NavaiaForge dashboard. Use it:

- **Standalone** — run everything from code: scripts, services, CI, notebooks, internal tools. No dashboard required.
- **Alongside the UI** — anything you build in code appears in the dashboard immediately, and anything built in the dashboard is reachable from the SDK. Same workforces, same agents, same tasks. Two views over one backend.

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
kb = client.knowledge.create(name="Product Docs")
client.knowledge.upload_document(kb_id=kb.id, file_path="./handbook.pdf")
client.workforces.attach_knowledge(workforce_id=wf.id, knowledge_base_id=kb.id)
# Every agent in the workforce can now retrieve from "Product Docs" via RAG.
```

### Give the team shared tools

```python
tool = client.tools.create(
    name="github-search",
    type="http",
    config={"base_url": "https://api.github.com", "auth": "bearer"},
)
client.tools.attach_to_workforce(tool_id=tool.id, workforce_id=wf.id)
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

ws = NavaiaForgeWs(HttpConfig(base_url="http://localhost:8000", api_key="nf_..."))
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
client.observability.summary()                       # tokens / spend overview
client.observability.cost(group_by="model")          # cost broken down by model
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
| **agents** | Full CRUD; browse `featured`, `clone`, `export`, attach/detach to workforces, list members | Compose specialists with their own roles, models, and instructions |
| **tasks** | Submit, approve, reject, retry, stream logs, `wait_for_completion` | Hand work to the team and get results — sync or async |
| **conversations** | Open chats with workforces, send messages targeted at specific agents | Build chat UIs, support bots, interactive assistants |
| **knowledge** | Knowledge bases, document upload, semantic search, featured KBs, downloads | Ground agents in your own data via RAG |
| **templates** | Workforce templates + `templates.agents` for agent templates | Don't rebuild the same team twice; instantiate from a blueprint |
| **tools** | Full CRUD over tools (HTTP, MCP, code-exec, custom), featured discovery, attach/detach | Give the workforce hands — let agents call APIs, run code, hit external systems |
| **integrations** | Manage plugin integrations: list installed, browse `list_plugins`, CRUD | Connect Slack, GitHub, Linear, and other third-party services |
| **setup** | `options`, `validate`, `complete` | First-run onboarding, provider configuration, key validation |
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
  baseUrl: "http://localhost:8000", // point at your NavaiaForge instance
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
    base_url="http://localhost:8000",  # point at your NavaiaForge instance
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

- [Setup Guide](./docs/SETUP.md) — backend, SDK install, framework interop (LangGraph, LangChain, CrewAI, …)
- API Reference — _coming soon_
- Platform Guide — _coming soon_
- [Contributing](./CONTRIBUTING.md)

---

## Contributing

We welcome contributions. Please read our [Contributing Guide](./CONTRIBUTING.md) and sign our [Contributor License Agreement](./CLA.md) before submitting a pull request.

---

## License

This project is licensed under the [MIT License](./LICENSE).

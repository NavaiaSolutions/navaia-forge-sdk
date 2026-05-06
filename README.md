# NavaiaForge SDK

**Build, deploy, and orchestrate AI workforces — programmatically.**

[![npm version](https://img.shields.io/npm/v/@navaia/forge)](https://www.npmjs.com/package/@navaia/forge)
[![PyPI version](https://img.shields.io/pypi/v/navaia-forge)](https://pypi.org/project/navaia-forge/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)

Official SDKs for the [NavaiaForge](https://navaia.com) platform.

The SDK is a **first-class client for the same NavaiaForge backend that powers the web UI**. You can use it:

- **Standalone** — drive everything from code, scripts, CI, notebooks, or your own backend; no NavaiaForge UI required.
- **Alongside the UI** — anything you create in the dashboard is reachable from the SDK, and vice versa. Build a workforce in code, monitor it in the browser. Spin one up in the UI, run it from a cron job. Same workforces, same agents, same data.

---

## Why use it

- **Headless automation.** Run agents from CI, schedulers, or your existing services without touching a browser.
- **Real-time orchestration.** Tasks, agent status, and chat messages stream over a WebSocket so your code reacts the moment something happens.
- **Typed end-to-end.** TypeScript types and Pydantic v2 models for every resource — IDE autocomplete and runtime validation included.
- **Same surface as the UI.** Every workforce, agent, task, conversation, knowledge base, integration, tool, and template the dashboard exposes is available here.
- **Extensible.** Build custom UIs, internal tools, dashboards, Slack bots, agents-as-API, automated pipelines — all on top of the official client.

---

## Installation

### TypeScript / JavaScript

```bash
npm install @navaia/forge
```

### Python

```bash
pip install navaia-forge
```

---

## Quick Start

### TypeScript

```ts
import { NavaiaForge } from "@navaia/forge";

const nf = new NavaiaForge({
  apiKey: "nf_your_api_key",
  baseUrl: "https://api.navaia.com",
});

const workforce = await nf.workforces.create({
  name: "Research Team",
  description: "Multi-agent research assistant",
});

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

```python
from navaia_forge import NavaiaForgeClient

client = NavaiaForgeClient(
    base_url="https://api.navaia.com",
    api_key="nf_your_api_key",
)

workforce = client.workforces.create(
    name="Research Team",
    description="Multi-agent research assistant",
)

agent = client.agents.create(
    workforce_id=workforce.id,
    name="Researcher",
    role="research",
    instructions="Find and summarize information on any given topic.",
    model_provider="anthropic",
    model_name="sonnet",
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

## Feature catalog

Every namespace below is available on both `client` (Python) and `nf` (TypeScript).

| Namespace | What you can do |
|---|---|
| `workforces` | Create, list, fetch (`get` / `get_full`), update, delete workforces. Manage edges (agent-to-agent connections). Link/unlink tools and knowledge bases. |
| `agents` | Full CRUD. Browse `featured` agents, `clone` and `export` agents, attach/detach to workforces, list workforce members. |
| `tasks` | Submit tasks, `approve`, `reject`, `retry`. Stream task logs. `wait_for_completion()` blocks with configurable polling and timeout. |
| `conversations` | Open conversations against a workforce, list message history, send messages targeted at a specific agent. |
| `knowledge` | Create knowledge bases, upload documents, semantic `search`, `featured` lists, document `download`, deletion. |
| `templates` | Browse and instantiate workforce templates; nested `templates.agents` for agent templates. Build your own templates and publish them. |
| `tools` | Full CRUD over tools (HTTP, MCP, code-executor, etc.), `featured` discovery, attach/detach to workforces. |
| `integrations` | Manage third-party plugin integrations: list installed, browse `list_plugins()`, create/update/delete. |
| `setup` | Onboarding helpers: read setup `options`, `validate` an API key/provider config, `complete` first-run setup. |
| `observability` | Token-usage `summary`, multi-dimensional `cost` breakdowns, per-agent `agent_metrics`, RL `agent_evaluations`, manual `log_token_usage`. |
| `auth` | `me`, email/password `register` / `login` / `refresh`, API-key `create_key` / `validate`, helpers for Google/GitHub OAuth start URLs. |

### Real-time events (WebSocket)

Both SDKs ship a WebSocket client that subscribes to the same event stream the dashboard uses.

```ts
nf.ws.on("task:status", (evt) => console.log(evt.task_id, evt.status));
nf.ws.on("agent:status", (evt) => console.log(evt.agent_id, evt.status));
nf.ws.on("chat:message", (evt) => console.log(evt.role, evt.content));
nf.ws.connect();
```

```python
from navaia_forge import NavaiaForgeWs, HttpConfig

ws = NavaiaForgeWs(HttpConfig(base_url="https://api.navaia.com", api_key="nf_..."))
ws.on("task:status", lambda e: print(e["task_id"], e["status"]))
ws.connect()
ws.run_forever()
```

---

## Common workflows

### Build a multi-agent workforce in code

```python
wf = client.workforces.create(name="Code Review Team")
reviewer = client.agents.create(workforce_id=wf.id, name="Reviewer", role="review", instructions="...")
tester = client.agents.create(workforce_id=wf.id, name="Tester", role="qa", instructions="...")
client.workforces.create_edge(workforce_id=wf.id, source_agent_id=reviewer.id, target_agent_id=tester.id)
```

### Use a pre-built template

```python
result = client.templates.instantiate(template_id="engineering-workforce", name="My Team")
print(result.workforce_id)
```

### Ship a knowledge-grounded agent

```python
kb = client.knowledge.create(name="Product Docs")
client.knowledge.upload_document(kb_id=kb.id, file_path="./handbook.pdf")
client.workforces.attach_knowledge(workforce_id=wf.id, knowledge_base_id=kb.id)
```

### Drive everything from CI

API keys are first-class. Generate one with `client.auth.create_key("ci")` (or in the dashboard), drop it into your CI secret store, and the rest is just HTTP.

### Use it next to the UI

Anything you build with the SDK shows up in the NavaiaForge dashboard immediately — same workforces, agents, tasks, conversations, knowledge, integrations. Run a long-running task from the UI, monitor it from a notebook. Spin a workforce up in code, hand the URL to a teammate. The SDK and UI are two views over one backend.

---

## Templates

Pre-built workforce templates live in [`templates/`](./templates/):

- **Engineering Workforce** — code review, testing, deployment agents
- **Navaia Workforce** — general-purpose multi-agent team
- **QA Workforce** — automated testing and quality assurance

Use them via:

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

- [API Reference](https://docs.navaia.com/api)
- [Platform Guide](https://docs.navaia.com/guide)
- [Contributing](./CONTRIBUTING.md)

---

## Contributing

We welcome contributions. Please read our [Contributing Guide](./CONTRIBUTING.md) and sign our [Contributor License Agreement](./CLA.md) before submitting a pull request.

---

## License

This project is licensed under the [AGPL-3.0 License](./LICENSE).

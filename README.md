# NavaiaForge SDK

**Your AI Workforce Platform**

[![npm version](https://img.shields.io/npm/v/@navaia/forge)](https://www.npmjs.com/package/@navaia/forge)
[![PyPI version](https://img.shields.io/pypi/v/navaia-forge)](https://pypi.org/project/navaia-forge/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)

Official SDKs for the [NavaiaForge](https://navaia.com) platform. Build, deploy, and orchestrate AI workforces programmatically.

---

## Installation

### JavaScript / TypeScript

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

```typescript
import { NavaiaForge } from "@navaia/forge";

const nf = new NavaiaForge({
  apiKey: "nf_your_api_key",
  baseUrl: "https://api.navaia.com",
});

// Create a workforce
const workforce = await nf.workforces.create({
  name: "My Workforce",
  description: "Getting started with NavaiaForge",
});

// Add an agent
const agent = await nf.agents.create({
  workforce_id: workforce.id,
  name: "Researcher",
  role: "research",
  instructions: "Find and summarize information on any given topic.",
  model_provider: "anthropic",
  model_name: "sonnet",
});

// Submit a task and wait for results
const task = await nf.tasks.create({
  workforce_id: workforce.id,
  title: "Research AI trends",
  agent_id: agent.id,
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

# Create a workforce
workforce = client.workforces.create(
    name="My Workforce",
    description="Getting started with NavaiaForge",
)

# Add an agent
agent = client.agents.create(
    workforce_id=workforce["id"],
    name="Researcher",
    role="research",
    instructions="Find and summarize information on any given topic.",
    model_provider="anthropic",
    model_name="sonnet",
)

# Submit a task and wait for results
task = client.tasks.create(
    workforce_id=workforce["id"],
    title="Research AI trends",
    agent_id=agent["id"],
)

result = client.tasks.wait_for_completion(task["id"])
print(result["result"])
```

---

## SDK Resources

Both SDKs provide access to the full NavaiaForge API:

| Resource | Description |
|----------|-------------|
| **Workforces** | Create and manage AI workforces |
| **Agents** | Configure agents with roles, instructions, and models |
| **Tasks** | Submit tasks, approve/reject, retry, and poll for results |
| **Conversations** | Chat with agents in real-time |
| **Knowledge** | Upload documents for RAG-powered agents |
| **Templates** | Browse and instantiate pre-built workforce templates |
| **Observability** | Monitor token usage, costs, and performance metrics |
| **Integrations** | Connect third-party services |

The TypeScript SDK also includes a **WebSocket client** for real-time events:

```typescript
nf.ws.on("task:status", (event) => {
  console.log(`Task ${event.task_id}: ${event.status}`);
});
nf.ws.connect();
```

---

## Templates

Pre-built workforce templates are available in the [`templates/`](./templates/) directory:

- **Engineering Workforce** -- Code review, testing, and deployment agents
- **Navaia Workforce** -- General-purpose multi-agent team
- **QA Workforce** -- Automated testing and quality assurance

Use templates via the SDK:

```typescript
const workforce = await nf.templates.instantiate("engineering-workforce", "My Team");
```

---

## Examples

See the [`examples/`](./examples/) directory for complete, runnable examples:

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

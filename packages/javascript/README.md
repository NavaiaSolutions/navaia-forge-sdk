# @navaia/forge

Official TypeScript / JavaScript SDK for the [NavaiaForge](https://navaia.com) AI workforce platform — a typed, real-time client for building **multi-agent AI workforces** that work like teams.

Use it **standalone** (Node services, scripts, edge functions, CI) or **alongside the NavaiaForge dashboard**. Both speak to the same backend, so anything created in code shows up in the UI and vice versa.

[![npm version](https://img.shields.io/npm/v/@navaia/forge)](https://www.npmjs.com/package/@navaia/forge)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

---

## Install

```bash
npm install @navaia/forge
# or
pnpm add @navaia/forge
# or
yarn add @navaia/forge
```

Requires Node.js **>= 18**.

---

## Quickstart

```ts
import { NavaiaForge } from "@navaia/forge";

const nf = new NavaiaForge({
  apiKey: "nf_your_api_key",
  baseUrl: "http://localhost:8000", // point at your NavaiaForge instance
});

// 1. Create a workforce
const workforce = await nf.workforces.create({ name: "Research Team" });

// 2. Add a specialist agent
const agent = await nf.agents.create({
  workforce_id: workforce.id,
  name: "Researcher",
  role: "research",
  instructions: "Find and summarize information on any given topic.",
  model_provider: "anthropic",
  model_name: "sonnet",
});

// 3. Submit a task and wait for completion
const task = await nf.tasks.create({
  workforce_id: workforce.id,
  agent_id: agent.id,
  title: "Survey 2025 LLM efficiency papers",
});
const result = await nf.tasks.waitForCompletion(task.id);
console.log(result.status, result.result);
```

---

## What's in the SDK

Every namespace below is fully typed.

| Namespace | What it does |
|---|---|
| `nf.workforces` | CRUD workforces; manage edges between agents; link tools and knowledge bases |
| `nf.agents` | Full CRUD; browse `featured`, `clone`, `export`, attach/detach to workforces |
| `nf.tasks` | Submit, approve, reject, retry, stream logs, `waitForCompletion` |
| `nf.conversations` | Open chats with workforces, target messages at specific agents |
| `nf.knowledge` | Knowledge bases, document upload, semantic search, downloads |
| `nf.templates` | Workforce + agent templates: don't rebuild the same team twice |
| `nf.tools` | Full CRUD over tools (HTTP, MCP, code-exec, custom); attach/detach |
| `nf.integrations` | Plugin integrations: Slack, GitHub, Linear, etc. |
| `nf.setup` | First-run onboarding, provider config, key validation |
| `nf.observability` | Token usage, cost breakdowns, per-agent metrics, RL evaluations |
| `nf.auth` | `me`, register/login/refresh, API-key creation/validation, OAuth helpers |
| `nf.ws` | Real-time stream: task status, agent status, chat messages, system events |

---

## Real-time updates

```ts
import { NavaiaForgeWs } from "@navaia/forge";

const ws = new NavaiaForgeWs({
  apiKey: "nf_...",
  baseUrl: "http://localhost:8000",
});

ws.on("task:status",  (e) => console.log("task:",  e.task_id, e.status));
ws.on("agent:status", (e) => console.log("agent:", e.agent_id, e.status));
ws.on("chat:message", (e) => console.log(e.role, e.content));

await ws.connect();
```

---

## Errors

All API errors extend `NavaiaForgeError`:

```ts
import {
  NavaiaForgeError,
  AuthenticationError,
  PermissionError,
  NotFoundError,
  RateLimitError,
  TimeoutError,
} from "@navaia/forge";

try {
  await nf.tasks.create({ workforce_id: "missing" });
} catch (err) {
  if (err instanceof NotFoundError) {
    // 404 — handle gracefully
  } else if (err instanceof RateLimitError) {
    // 429 — back off and retry
  } else {
    throw err;
  }
}
```

---

## Links

- Repository: <https://github.com/NavaiaSolutions/navaia-forge-sdk>
- Issues: <https://github.com/NavaiaSolutions/navaia-forge-sdk/issues>
- Python SDK: [`navaia-forge`](https://pypi.org/project/navaia-forge/)

## License

[MIT](./LICENSE) © NavaiaSolutions

# @navaia/forge

Official TypeScript / JavaScript client for the [NavaiaForge](https://navaia.com) AI workforce platform — a typed, real-time client for building **multi-agent AI workforces** that work like teams.

Use it **standalone** (Node services, CLIs, edge functions, browsers) or **alongside the NavaiaForge dashboard**. Both speak to the same backend, so anything created in code shows up in the UI and vice versa.

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

Your options: run it on your **laptop** (dev / learning), on your **own VM or cluster** (production), or **air-gapped on-prem** (compliance). Same image, same SDK code, just a different `baseUrl`.

```bash
curl -fLO https://raw.githubusercontent.com/NavaiaSolutions/NavaiaForge/main/docker-compose.dist.yml
# create .env with your NAVAIA_LICENSE token, then:
docker compose -f docker-compose.dist.yml up -d
# → API at http://localhost:8001
```

Always point `baseUrl` at your local backend (e.g. `http://localhost:8001`). Full walkthrough: [`SETUP.md`](https://github.com/NavaiaSolutions/navaia-forge-sdk/blob/main/SETUP.md).

## Installation

```bash
npm install @navaia/forge
```

## Quickstart

```ts
import { NavaiaForge } from "@navaia/forge";

const nf = new NavaiaForge({
  baseUrl: "http://localhost:8001", // the backend you started with `docker compose up`
  apiKey: "nf_...",
});

// Build the team
const wf = await nf.workforces.create({ name: "Code Review Team" });
const reviewer = await nf.agents.create({
  workforce_id: wf.id,
  name: "Reviewer",
  role: "review",
  instructions: "Review PRs for correctness and security.",
  model_provider: "anthropic",
  model_name: "sonnet",
});
const tester = await nf.agents.create({
  workforce_id: wf.id,
  name: "Tester",
  role: "qa",
  instructions: "Generate and run tests for approved diffs.",
  model_provider: "anthropic",
  model_name: "sonnet",
});

// Wire reviewer → tester
await nf.workforces.edges.create({
  workforce_id: wf.id,
  source_agent_id: reviewer.id,
  target_agent_id: tester.id,
});

// Hand work to the team
const task = await nf.tasks.create({
  workforce_id: wf.id,
  title: "Review PR #482 and add tests",
});
const final = await nf.tasks.waitForCompletion(task.id);
console.log(final.status, final.result);
```

All resource methods return typed results. Errors throw `NavaiaForgeError` (or a subclass: `NotFoundError`, `RateLimitError`, `AuthenticationError`, `PermissionError`, `TimeoutError`).

## Real-time events

```ts
import { NavaiaForgeWs } from "@navaia/forge";

const ws = new NavaiaForgeWs({
  apiKey: "nf_...",
  baseUrl: "http://localhost:8001",
  timeout: 60_000,
});
// SDK channels (re-mapped from raw backend event types):
//   "task:status"   ← task_created/completed/failed/updated
//   "agent:status"  ← agent_status_changed
//   "chat:message"  ← chat_message
ws.on("task:status",  (e) => console.log("task:",  e.task_id, e.status));
ws.on("agent:status", (e) => console.log("agent:", e.agent_id, e.status));
ws.on("chat:message", (e) => console.log(e.role, e.content_preview));
ws.connect();
```

## What you can do

| Namespace | What it does | Why you'd use it |
|---|---|---|
| `nf.workforces` | CRUD; nested `edges` sub-resource | Define the team and how work flows through it |
| `nf.agents` | CRUD; `listFeatured`, `clone`, `export`; attach/detach to workforces | Compose specialists with their own models and instructions |
| `nf.tasks` | `create`, `approve`, `reject`, `retry`, `logs`, `waitForCompletion` | Hand work to the team, sync or async |
| `nf.conversations` | Open chats, send messages targeted at agents | Build chat UIs / interactive assistants |
| `nf.knowledge` | Knowledge bases, document upload, semantic `search`, `featured`, download | Ground agents in your data via RAG |
| `nf.templates` | Workforce templates + `templates.agents` for agent templates | Don't rebuild the same team twice |
| `nf.tools` | Full CRUD, `listFeatured`, attach/detach to workforces | Give the team hands (HTTP, MCP, code-exec, custom) |
| `nf.integrations` | `list`, `listPlugins`, CRUD | Connect Slack / GitHub / Linear / other plugins |
| `nf.setup` | `options`, `validate`, `complete` | First-run onboarding / provider configuration |
| `nf.observability` | `summary`, `cost`, `agentMetrics`, `agentEvaluations`, `logTokenUsage` | See what the team is doing and what it costs |
| `nf.auth` | `me`, `register`, `login`, `refresh`, `createKey`, `validate`, OAuth URL helpers | Build your own UI on top of NavaiaForge |

## LangGraph integration

Already have a LangGraph workforce? Run it inside Forge with one wrapper — keep your graph code, gain Forge observability and backend access.

```bash
npm install @navaia/forge @langchain/core @langchain/langgraph
```

```ts
import { NavaiaForge } from "@navaia/forge";
import {
  LangGraphWorkforce,
  getForgeContext,
} from "@navaia/forge/integrations/langgraph";

// Inside any node — no special wiring beyond the standard `config` arg.
async function searchNode(state: MyState, config: any) {
  const forge = getForgeContext(config);
  const hits = await forge.client.knowledge.search(
    forge.workforceId!,
    state.query,
  );
  return { hits: hits };
}

// Wrap a compiled graph; the wrapper installs the Forge callback and
// injects ForgeContext on RunnableConfig.configurable for you.
const wf = new LangGraphWorkforce(myCompiledGraph, new NavaiaForge({
  baseUrl: "http://localhost:8001",
  apiKey: "nf_...",
}), { workforceId: "wf_existing" });

const result = await wf.run({ query: "..." }, { taskId: "task_123" });
```

Token usage from every LLM call lands on the workforce's cost dashboard.

## Standalone or with the UI

- **Standalone:** the SDK is sufficient on its own — no dashboard required. Drive everything from TypeScript: services, scripts, CLIs, browser apps, edge functions.
- **Alongside the dashboard:** anything you create programmatically appears in the NavaiaForge UI immediately, and anything created in the UI is reachable from `nf.*`. Two views over one backend.

## Development

```bash
npm install
npm run typecheck
npm test
npm run build
```

## License

MIT

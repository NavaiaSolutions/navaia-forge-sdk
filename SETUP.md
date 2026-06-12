# NavaiaForge SDK — Setup Guide

This guide gets you from zero to "calling NavaiaForge from any repo on any
machine" in a few minutes. It covers:

1. Standing up the backend on your own infrastructure (Docker)
2. Installing the SDK into any project (Python or TypeScript)
3. Verifying end-to-end with a real workforce
4. Using NavaiaForge as a complete platform (the recommended path)
5. Bringing your own framework — LangGraph, LangChain, CrewAI, or anything else

---

## How the pieces fit

NavaiaForge ships in two layers. They are versioned, released, and used
independently:

```
   ┌─────────────────────────────┐         ┌────────────────────────────┐
   │  YOUR CODE / NOTEBOOK / CI  │  HTTP+  │  NavaiaForge backend       │
   │  + NavaiaForge SDK          │   WS    │  (Docker, self-hosted)     │
   │  (pip install navaia-forge) │ ──────▶ │  ghcr.io/.../forge-backend │
   │  (npm install @navaia/forge)│         │  + Postgres / Weaviate /…  │
   └─────────────────────────────┘         └────────────────────────────┘
        open source (this repo)                 closed-source image
```

- **The SDK** (this repo) is open source — the Python package on PyPI is
  Apache-2.0 and the JavaScript package on npm is MIT. The repo umbrella
  is AGPL-3.0 (see `LICENSE`). It's a typed HTTP/WebSocket client over
  the platform API. Nothing more.
- **The backend** is distributed as a signed Docker image on GitHub
  Container Registry. The Python source is compiled to native extensions
  before the image is built, so the runtime image carries no readable
  application code. You self-host it; you do not need source access. See
  [§ "About the backend image"](#about-the-backend-image) for what that
  actually means.

You can run any combination:

| Scenario | Backend | SDK |
|---|---|---|
| Local dev, single machine | `docker compose up` on your laptop | `pip install navaia-forge` in another project |
| Production self-host | Docker on your VM / cluster | SDK in any service that needs to talk to it |
| Hosted (when available) | `https://api.navaia.com` | Same SDK, just a different `base_url` |

---

## Step 1 — Run the backend

The canonical, end-to-end self-hosting instructions live with the backend:
**[`NavaiaSolutions/NavaiaForge › docs/SELF_HOSTING.md`](https://github.com/NavaiaSolutions/NavaiaForge/blob/main/docs/SELF_HOSTING.md)**.

If you've never set it up before, read that file. The TL;DR below gets you
running on a clean machine, but the linked doc is authoritative for
upgrades, air-gapped installs, backups, and license enforcement modes.

### TL;DR

You need:

- Docker 24+ with Compose v2 (`docker compose`, not `docker-compose`)
- A NavaiaForge license token from `licensing@navaia.com` (a JWT starting
  with `eyJ`)
- About 4 GB RAM and 2 vCPUs for a comfortable single-node deploy

A copy of the compose file ships in this repo as
[`docker-compose.dist.yml`](docker-compose.dist.yml), or pull the latest:

```bash
# Pull the compose file (no source clone needed)
curl -fLO https://raw.githubusercontent.com/NavaiaSolutions/NavaiaForge/main/docker-compose.dist.yml

# Configure
cat > .env <<'EOF'
NAVAIA_LICENSE=eyJhbGciOiJSUzI1NiIs...your-token...
NAVAIA_LICENSE_ENFORCEMENT=strict
NAVAIA_BACKEND_VERSION=v1.0.0
NAVAIA_FRONTEND_VERSION=v1.0.0
POSTGRES_USER=navaia_forge
POSTGRES_PASSWORD=change-me-please
POSTGRES_DB=navaia_forge
API_PORT=8001
UI_PORT=3030
NEXT_PUBLIC_API_URL=http://localhost:8001
NEXT_PUBLIC_WS_URL=ws://localhost:8001
SECRET_KEY=$(openssl rand -hex 32)
EOF

# Start
docker compose -f docker-compose.dist.yml up -d

# Verify
curl http://localhost:8001/health         # → {"status":"healthy",...}
curl http://localhost:8001/health/ready   # → {"status":"ready",...}
```

Your API is now at `http://localhost:8001`. Optional console at
`http://localhost:3030`.

### Mint an API key for the SDK

The SDK authenticates with an `nf_...` API key. Two ways to get one:

- **Console** — open `http://localhost:3030`, log in, generate a key in
  Settings → API Keys.
- **SDK** — once you have a session token from logging in, you can mint
  keys programmatically: `client.auth.create_key("ci-runner")`.

Treat the key like any production secret. Rotate via the console.

---

## Step 2 — Install the SDK

The SDK is published. You don't need this repo cloned to use it.

### Python

```bash
pip install navaia-forge        # Python ≥ 3.10
```

```python
from navaia_forge import NavaiaForgeClient

client = NavaiaForgeClient(
    base_url="http://localhost:8001",   # your backend
    api_key="nf_…",                     # from step 1
)
```

The SDK targets `{base_url}/api/v1/...` for HTTP and `{base_url}/ws` for
the WebSocket stream — pass the **bare** backend URL, not the
`/api/v1` path.

Optional extras:

```bash
pip install "navaia-forge[langgraph]"   # enables LangGraph integration
```

### TypeScript / JavaScript

```bash
npm install @navaia/forge
```

```ts
import { NavaiaForge } from "@navaia/forge";

const nf = new NavaiaForge({
  baseUrl: "http://localhost:8001",
  apiKey:  "nf_…",
});
```

Works in Node ≥ 18 and in modern browsers (CORS configured on the
backend; see `SELF_HOSTING.md` for production CORS pinning).

---

## Step 3 — Sanity check

Run this from any repo on your machine. It uses no source from this
repo — only the published packages.

```python
from navaia_forge import NavaiaForgeClient

client = NavaiaForgeClient(
    base_url="http://localhost:8001",
    api_key="nf_…",
)

wf = client.workforces.create(name="Hello Forge")
print("created workforce:", wf.id)

agent = client.agents.create(
    workforce_id=wf.id,
    name="Echo",
    role="generalist",
    instructions="Repeat the user's request, then answer it.",
    model_provider="anthropic", model_name="claude-sonnet-4-6",
)

task = client.tasks.create(workforce_id=wf.id, title="Say hello.")
final = client.tasks.wait_for_completion(task.id)
print(final.status, final.result)
```

If this prints a completed task, your end-to-end install is good.

---

## Recommended path — let NavaiaForge be the platform

The SDK is a thin client, but the backend is doing real work:

- **Workforce graph execution** — agents, edges, routing, retries, approval gates
- **Shared knowledge bases** — RAG over your documents, scoped to a workforce
- **Shared tools** — HTTP, MCP, code execution; defined once, reused by every agent
- **Real-time event stream** — task status, agent status, chat messages over WebSocket
- **Observability** — tokens, cost, per-agent metrics, RL evaluations
- **Conversations** — chat UIs scoped to a workforce, targeted at specific agents
- **Templates** — pre-built workforces (engineering, QA, generalist) you can instantiate in one call
- **Integrations** — Slack / GitHub / Linear / Telegram / Trello plugins, configured once at the workforce level

If you adopt these primitives, you are not writing routing logic, retry
logic, RAG plumbing, tool registries, or event buses. You're configuring
them and calling `tasks.create()`. That's the one-stop-shop value.

You can see the full namespace catalog in the
[main README](../README.md#feature-catalog).

---

## Sync local workforces to the cloud

You can run the backend **locally** (so the compute runs on your machine)
while still publishing to the live Fareegi cloud — for the marketplace,
collaboration, and the hosted visual UI. The SDK is the orchestrator: it
makes the HTTP call to each backend, so the two never talk to each other.

Every entity carries a permanent `origin_id`, so a workforce can make a
full round-trip — push to cloud, edit in the cloud UI, pull back — without
ever duplicating.

Point one client at your local backend and another at the cloud:

```python
import os
from navaia_forge import NavaiaForgeClient, SyncConflictError

local = NavaiaForgeClient(
    base_url="http://localhost:8001",
    api_key=os.environ["NAVAIA_LOCAL_API_KEY"],
)
cloud = NavaiaForgeClient(
    base_url="https://fareegi.navaia.sa",
    api_key=os.environ["NAVAIA_CLOUD_API_KEY"],
)
```

**Push** — export from local, import into cloud:

```python
result = local.sync.push(wf.id, remote=cloud)
print(result.action, result.workforce_id)   # "created" | "updated"
```

**Pull** — bring a marketplace purchase back down to run locally.
Re-pulling is safe: `origin_id` self-recognition updates in place instead
of creating a duplicate:

```python
pulled = local.sync.pull(cloud_workforce_id, remote=cloud)
```

**Conflict handling** — if the cloud copy changed since the last sync,
`push`/`import` raises `SyncConflictError` carrying both bundles. Either
keep the remote version (do nothing) or force-overwrite it:

```python
try:
    result = local.sync.push(wf.id, remote=cloud)
except SyncConflictError as exc:
    print("remote was modified:", exc.remote_bundle)
    result = local.sync.push(wf.id, remote=cloud, force=True)
```

**Portable bundles** — secrets are redacted, so you can also round-trip
through disk:

```python
local.sync.export_to_file(wf.id, "research_team.json")
# … later, on another machine …
cloud.sync.import_from_file("research_team.json")
```

A complete, runnable version lives in
[`examples/python/sync_local_to_cloud.py`](examples/python/sync_local_to_cloud.py).
The same surface exists in the TypeScript SDK as `nf.sync.push(...)` /
`nf.sync.pull(...)`.

---

## Bringing your own framework

Some teams want to keep an existing framework (LangGraph, LangChain,
CrewAI, AutoGen, LlamaIndex, Haystack, …) for *inside-an-agent* logic
while letting NavaiaForge handle the workforce-level concerns above.
That's supported — and in one case (LangGraph) we ship a first-class
adapter.

### LangGraph — first-class integration

LangGraph is the only framework with a built-in adapter today. It lets
you take a compiled LangGraph and run it as a NavaiaForge workforce
without re-architecting. Token usage and timing flow into Forge
observability automatically, and any node can call the Forge SDK
(knowledge search, tools, conversations) through an injected context.

```bash
pip install "navaia-forge[langgraph]" langgraph langchain-openai
```

```python
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

from navaia_forge import NavaiaForgeClient
from navaia_forge.integrations.langgraph import (
    LangGraphWorkforce, get_forge_context,
)

# IMPORTANT: annotate `config` as RunnableConfig — LangGraph only injects
# the config dict into nodes that explicitly opt in via this type hint.
def search_node(state: dict, config: RunnableConfig) -> dict:
    forge = get_forge_context(config)          # SDK auto-injected
    if forge.workforce_id:
        hits = forge.client.knowledge.search(forge.workforce_id, state["query"])
        return {"hits": [h.model_dump() for h in hits.results]}
    return {"hits": []}

def answer_node(state: dict, config: RunnableConfig) -> dict:
    llm = ChatOpenAI(model="gpt-4o-mini")
    context = "\n".join(h.get("content", "") for h in state.get("hits", []))
    return {"answer": str(llm.invoke(f"{state['query']}\n\n{context}").content)}

g = StateGraph(dict)
g.add_node("search", search_node); g.add_node("answer", answer_node)
g.set_entry_point("search"); g.add_edge("search", "answer"); g.add_edge("answer", END)

client = NavaiaForgeClient(base_url="http://localhost:8001", api_key="nf_…")
wf = LangGraphWorkforce(graph=g.compile(), client=client, name="research-team",
                        workforce_id="<your-forge-workforce-id>")
print(wf.run({"query": "What are NavaiaForge's design goals?"}))
```

A runnable version of this is in
[`examples/python/langgraph_workforce.py`](../examples/python/langgraph_workforce.py).

### LangChain, CrewAI, AutoGen, LlamaIndex, others — interop pattern

There's no dedicated adapter for these today, but the SDK is a plain
HTTP client — you can always run them alongside NavaiaForge. The pattern
is the same in every case:

> NavaiaForge owns the *outside* of the agent (which agents exist, how
> work routes between them, what knowledge / tools they share, what the
> task lifecycle looks like). The other framework owns the *inside* of
> a single agent (its prompting strategy, its chain composition, its
> reasoning loop).

A typical shape:

```python
from navaia_forge import NavaiaForgeClient
# Replace the next two lines with your framework of choice.
from crewai import Agent, Task, Crew

client = NavaiaForgeClient(base_url="http://localhost:8001", api_key="nf_…")

# 1. Forge owns the workforce, edges, knowledge, observability.
wf = client.workforces.create(name="Research Crew")
kb = client.knowledge.create(name="Industry Reports")
client.knowledge.upload_document(knowledge_base_id=kb.id, file_path="./reports.pdf")
client.knowledge.attach_to_workforce(workforce_id=wf.id, knowledge_base_id=kb.id)

# 2. Your framework drives reasoning *inside* one agent. It pulls
#    context out of Forge (RAG hits, tool defs) and pushes results back
#    (task records, conversation messages, usage logs).
hits = client.knowledge.search(wf.id, "Q3 market shifts")
crew = Crew(agents=[Agent(role="analyst", goal="Summarize", ...)],
            tasks=[Task(description=f"Summarize:\n{hits}")])
output = crew.kickoff()

# 3. Record the run on the Forge side so it lives in the workforce's
#    task history alongside everything else. Pass the framework's output
#    via metadata; observability rolls up cost from the SDK calls above.
client.tasks.create(
    workforce_id=wf.id,
    title="Q3 summary",
    description=str(output),
    metadata={"framework": "crewai"},
)
```

The same shape works for **LangChain** chains, **AutoGen** group chats,
**LlamaIndex** query engines, or anything else: pull primitives out of
Forge, run them through your framework, push results back. You give up
some of the unified-observability story (the framework's internal LLM
calls aren't auto-instrumented), but everything that crosses the SDK
boundary is captured.

If the unified observability story matters and you're willing to wrap
your framework like LangGraph is wrapped, the
[`integrations/langgraph/`](../packages/python/navaia_forge/integrations/langgraph/)
package is a good model to copy.

---

## About the backend image

The backend is distributed as a closed-source Docker image. Practical
implications:

- **No source ships with the image.** Application Python files are
  compiled to native extensions during the image build; the runtime
  image carries `.so` files, not `.py` source. You cannot read the
  orchestration / routing logic out of the image, and neither can a
  customer who downloads it. This is a deterrent against trivial
  inspection — not a cryptographic guarantee.
- **The license check is offline.** A short JWT signed by Navaia's
  private key is verified locally against a public key baked into the
  image at build time. There are no callbacks, no telemetry, and the
  check works in air-gapped environments.
- **Your data stays in your stack.** Postgres, Weaviate, Redis are
  standard upstream images you control. Workforce definitions, tasks,
  knowledge base contents, and chat history live in your database — the
  Navaia-shipped containers don't phone home.

If you need source-level access for compliance or deep customization,
contact `licensing@navaia.com` to discuss a source license. The default
ship is binary-only.

---

## Common environment variables

These are the variables the SDK and the backend look at most often.

### SDK side

| Var | Used by | Purpose |
|---|---|---|
| `NAVAIA_FORGE_BASE_URL` | Examples in `examples/` | The backend URL (e.g. `http://localhost:8001`). The SDK constructor takes `base_url=` directly — env vars are an example convention, not built into the client. |
| `NAVAIA_FORGE_API_KEY`  | Examples in `examples/` | Your `nf_…` API key. |
| `NAVAIA_FORGE_WORKFORCE_ID` | LangGraph example | Optional: bind a graph to an existing workforce. |
| `NAVAIA_FORGE_TASK_ID` | LangGraph example | Optional: report graph progress against an existing task. |

### Backend side (excerpt — see `SELF_HOSTING.md` for the full list)

| Var | Purpose |
|---|---|
| `NAVAIA_LICENSE` | The JWT issued by Navaia. Required. |
| `NAVAIA_LICENSE_ENFORCEMENT` | `strict` (default), `warn`, or `disabled`. Logged at startup. |
| `NAVAIA_BACKEND_VERSION` / `NAVAIA_FRONTEND_VERSION` | Image tag pins. |
| `SECRET_KEY` | App secret. ≥ 32 random bytes. |
| `POSTGRES_*`, `API_PORT`, `UI_PORT`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL` | Standard service plumbing. |

---

## Troubleshooting

**`pip install navaia-forge` fails with `requires a different Python: 3.9.x`**
The SDK requires Python ≥ 3.10. Use `python3.10`/`3.11`/`3.12` to create
the venv: `python3.12 -m venv .venv && .venv/bin/pip install navaia-forge`.

**SDK calls fail with `ConnectionError` / `ECONNREFUSED`**
The backend isn't reachable at `base_url`. Check
`docker compose -f docker-compose.dist.yml ps` and
`curl http://localhost:8001/health`. If the API container is restarting,
check its logs — most often it's an invalid `NAVAIA_LICENSE`.

**SDK calls succeed but return `401 Unauthorized`**
The API key is wrong or revoked. Mint a new one in the console or via
`client.auth.create_key("…")` after logging in.

**Backend container exits with `LicenseInvalid` / `LicenseExpired`**
Your token is bad or past its `exp`. Email `licensing@navaia.com` for a
replacement. The container exits on purpose so a misconfigured deploy
fails loudly instead of silently running unauthorized.

**WebSocket events never arrive**
Check that `NEXT_PUBLIC_WS_URL` (browser-facing) and the SDK's `base_url`
(server-facing) both reach the same API container. Behind a reverse
proxy you also need WebSocket upgrade headers configured (`Upgrade`,
`Connection`).

**`pip install "navaia-forge[langgraph]"` succeeds but `import navaia_forge.integrations.langgraph` fails**
The extras pin compatible LangChain/LangGraph minor versions; if you
have an older `langgraph` already installed in the env, install in a
fresh venv or upgrade it explicitly.

For anything else that looks like a bug, open an issue on
[`navaia-forge-sdk`](https://github.com/NavaiaSolutions/navaia-forge-sdk/issues)
(SDK behaviour) or email `support@navaia.com` (backend / licensing).

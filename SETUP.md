# NavaiaForge SDK — Setup Guide

This guide gets you from zero to running AI workforces in a few minutes.

**The default model:** you run the backend on your own machine. Your
compute, your LLM keys, your data. The cloud dashboard at
`fareegi.navaia.sa` is an optional display layer — sync results there
when you want to visualise or share, but all execution happens locally.

---

## Architecture

```
Your machine (you own this)                   fareegi.navaia.sa (optional)
┌────────────────────────────────────┐        ┌─────────────────────────┐
│  Backend container (Docker)        │  sync  │  Dashboard / UI         │
│  + Postgres / Weaviate / Redis     │ ─────▶ │  Marketplace catalog    │
│  + Agent CLI (claude / navaia-code)│        │  Published workforces   │
│  + YOUR LLM keys                   │        │  User accounts          │
│                                    │        │                         │
│  ← Runs everything:               │        │  ← Display only:        │
│    agent execution, LLM calls,     │        │    no execution         │
│    tasks, RAG, orchestration       │        │    no LLM keys needed   │
└────────────────────────────────────┘        └─────────────────────────┘
         ▲                                              ▲
         │ SDK (this repo)                              │ browser
         │ pip install navaia-forge                     │
```

There is no local UI. The dashboard lives at `fareegi.navaia.sa` — use
`client.sync.push()` to send results there when you want to visualise
them.

- **You pay your LLM provider directly** — Anthropic, OpenRouter, or
  whatever you authenticate your agent CLI with. NavaiaForge never
  touches your model credentials.
- **Your data stays on your machine** — workforces, tasks, knowledge
  bases, conversations, agent outputs. Nothing leaves unless you
  explicitly `sync.push()` to the cloud.
- **The cloud is optional** — you can run entirely offline. The dashboard
  is there when you want to browse the marketplace, share a workforce,
  or see results in a visual UI.

> **Want managed hosting instead?** If you'd rather not run the backend
> yourself, contact `info@navaia.sa` for a managed deployment where we
> run the infrastructure on your behalf. This is not the default path.

---

## Step 1 — Run the backend locally

You need:

- Docker 24+ with Compose v2 (`docker compose`, not `docker-compose`)
- An OpenRouter API key (https://openrouter.ai/keys) or Claude Code CLI
- ~4 GB RAM, 2 vCPUs

```bash
# Clone the SDK repo (includes docker-compose.dist.yml and .env.example)
git clone https://github.com/NavaiaSolutions/navaia-forge-sdk.git
cd navaia-forge-sdk

# Configure
cp .env.example .env
# Edit .env — set SECRET_KEY, POSTGRES_PASSWORD, OPENROUTER_API_KEY

# Start
docker compose -f docker-compose.dist.yml up -d

# Verify
curl http://localhost:8001/health         # → {"status":"healthy",...}
```

Your backend is now at `http://localhost:8001`.

---

## Step 2 — Configure the agent runtime

The backend orchestrates agents but doesn't embed an LLM. It shells out
to a coding-agent CLI on the host machine. Pick one:

### Option A — Navaia Code (multi-model via OpenRouter)

```bash
# Install Navaia Code CLI
navaia-code --version

# Set your OpenRouter key (you pay OpenRouter directly)
export OPENROUTER_API_KEY=sk-or-v1-your-key
```

Create workforces with `runtime_mode="navaia_code"`.

### Option B — Claude Code (Anthropic)

```bash
# Install Claude Code
claude --version   # https://www.anthropic.com/claude-code

# Authenticate (your Anthropic subscription / API key)
claude login
```

Create workforces with `runtime_mode="claude_max"`.

That's the entire model-configuration story. The SDK never sees or
stores your LLM credentials.

---

## Step 3 — Install the SDK

```bash
pip install navaia-forge        # Python >= 3.10
```

```python
from navaia_forge import NavaiaForgeClient

client = NavaiaForgeClient(
    base_url="http://localhost:8001",   # your local backend
    api_key="nf_...",                   # from step 4
)
```

### TypeScript / JavaScript

```bash
npm install @navaia/forge
```

```ts
import { NavaiaForge } from "@navaia/forge";

const nf = new NavaiaForge({
  baseUrl: "http://localhost:8001",
  apiKey:  "nf_...",
});
```

---

## Step 4 — Create an API key

The SDK authenticates with an `nf_...` API key. Two ways to get one:

- **SDK** — after registering or logging in with email/password:
  ```python
  client = NavaiaForgeClient(base_url="http://localhost:8001")
  pair = client.auth.login(email="you@example.com", password="...")
  # Use the JWT to create a long-lived API key
  authed = NavaiaForgeClient(base_url="http://localhost:8001", api_key=pair.access_token)
  key = authed.auth.create_key("my-dev-key")
  print(key.api_key)  # nf_... — shown once, store it securely
  ```

---

## Step 5 — Build and run a workforce

```python
from navaia_forge import NavaiaForgeClient

client = NavaiaForgeClient(
    base_url="http://localhost:8001",
    api_key="nf_...",
)

# Create a workforce
wf = client.workforces.create(name="Research Team")

# Add agents
researcher = client.agents.create(
    workforce_id=wf.id,
    name="Researcher",
    role="research",
    instructions="Find and summarize information on any topic.",
    model_provider="anthropic",
    model_name="sonnet",
)
writer = client.agents.create(
    workforce_id=wf.id,
    name="Writer",
    role="writer",
    instructions="Turn research notes into a polished brief.",
    model_provider="anthropic",
    model_name="sonnet",
)

# Wire them: researcher → writer
client.workforces.edges.create(
    workforce_id=wf.id,
    source_agent_id=researcher.id,
    target_agent_id=writer.id,
)

# Run a task
task = client.tasks.create(workforce_id=wf.id, title="Survey 2025 LLM papers")
final = client.tasks.wait_for_completion(task.id)
print(final.status, final.result)
```

Everything runs on your machine — your backend, your LLM key, your
compute.

---

## Step 6 (optional) — Sync to the cloud dashboard

Once your workforce is running locally, you can push results to
`fareegi.navaia.sa` to see them in the hosted dashboard or publish to
the marketplace. This is **optional** — your workforce works without it.

```python
import os
from navaia_forge import NavaiaForgeClient

# Your local backend (where execution happens)
local = NavaiaForgeClient(
    base_url="http://localhost:8001",
    api_key=os.environ["NAVAIA_LOCAL_API_KEY"],
)

# The cloud dashboard (display only)
cloud = NavaiaForgeClient(
    base_url="https://fareegi.navaia.sa",
    api_key=os.environ["NAVAIA_CLOUD_API_KEY"],
)

# Push your workforce to the cloud for display
result = local.sync.push(workforce_id, remote=cloud)
print(f"Synced to cloud: {result.action}")

# Now visible at fareegi.navaia.sa in your dashboard
```

To get a cloud API key, sign up at `fareegi.navaia.sa` and generate
a key in Settings > API Keys on the dashboard.

### Publish to the marketplace

```python
# After pushing to cloud, publish it for others to discover
cloud.workforces.publish(
    result.workforce_id,
    tagline="Research team that finds and summarizes papers",
    category="research",
)
```

### Install from the marketplace

Other users can browse and install your published workforce:

```python
# Browse
listings = cloud.marketplace.list(category="research")

# Install into their cloud account
wf = cloud.marketplace.install(listings[0].id)

# Pull down to their local backend to actually run it
local.sync.pull(wf.id, remote=cloud)
```

A complete runnable example:
[`examples/python/sync_local_to_cloud.py`](examples/python/sync_local_to_cloud.py).

---

## Bringing your own framework

Some teams keep an existing framework (LangGraph, LangChain, CrewAI,
AutoGen) for inside-agent logic while NavaiaForge handles the
workforce-level concerns.

### LangGraph — first-class integration

```bash
pip install "navaia-forge[langgraph]" langgraph langchain-openai
```

```python
from navaia_forge import NavaiaForgeClient
from navaia_forge.integrations.langgraph import LangGraphWorkforce

client = NavaiaForgeClient(base_url="http://localhost:8001", api_key="nf_...")
wf = LangGraphWorkforce(
    graph=your_compiled_graph,
    client=client,
    name="research-team",
    workforce_id="<your-workforce-id>",
)
print(wf.run({"query": "What are NavaiaForge's design goals?"}))
```

Token usage and timing flow into Forge observability automatically.
See [`examples/python/langgraph_workforce.py`](examples/python/langgraph_workforce.py).

### Other frameworks — interop pattern

NavaiaForge owns the *outside* of the agent (routing, knowledge, tools,
observability). Your framework owns the *inside* (prompting, chain
composition, reasoning). Pull context from Forge, run it through your
framework, push results back:

```python
# 1. Forge provides the workforce shell + knowledge
hits = client.knowledge.search(kb_id, "Q3 market shifts")

# 2. Your framework does the reasoning
output = your_crew.kickoff(context=hits)

# 3. Record the result in Forge
client.tasks.create(workforce_id=wf.id, title="Q3 summary", description=str(output))
```

---

## About the backend image

The backend is a closed-source Docker image distributed via GHCR:

- **No source ships with the image** — Python files are compiled to
  native `.so` extensions. You cannot read application logic from the
  image.
- **No phone-home** — no callbacks, no telemetry. Works air-gapped.
- **Your data stays in your stack** — Postgres, Weaviate, Redis are
  standard images you control.

For source-level access, contact `info@navaia.sa`.

---

## Environment variables

### SDK side

| Var | Purpose |
|---|---|
| `NAVAIA_LOCAL_BASE_URL` | Your local backend (default `http://localhost:8001`) |
| `NAVAIA_LOCAL_API_KEY` | API key for your local backend |
| `NAVAIA_CLOUD_BASE_URL` | Cloud dashboard (default `https://fareegi.navaia.sa`) |
| `NAVAIA_CLOUD_API_KEY` | API key for the cloud (optional, for sync) |

### Backend side

| Var | Purpose |
|---|---|
| `SECRET_KEY` | App secret. >= 32 random bytes (`openssl rand -hex 32`). |
| `OPENROUTER_API_KEY` | For `navaia_code` runtime. You pay OpenRouter. |
| `POSTGRES_*`, `API_PORT` | Standard service plumbing |

---

## Troubleshooting

**`pip install navaia-forge` fails with `requires a different Python`**
The SDK requires Python >= 3.10. Use `python3.12 -m venv .venv`.

**SDK calls fail with `ConnectionError`**
Backend isn't running. Check `docker compose ps` and
`curl http://localhost:8001/health`.

**`401 Unauthorized`**
API key is wrong or revoked. Generate a new one in the dashboard.

**Tasks fail with "can't reach the language model"**
The agent CLI isn't configured. See Step 2 — you need either
`OPENROUTER_API_KEY` set or `claude login` done on the host.

**WebSocket events don't arrive**
Check that the SDK's `base_url` reaches the backend. Behind a reverse
proxy, configure WebSocket upgrade headers (`Upgrade`, `Connection`).

For bugs, open an issue on
[`navaia-forge-sdk`](https://github.com/NavaiaSolutions/navaia-forge-sdk/issues).
For backend/licensing: `info@navaia.sa`.

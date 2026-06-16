# NavaiaForge SDK Assessment

Build a workforce, run it, and publish it to the marketplace.

---

## What you will do

1. Run the NavaiaForge backend locally (Docker)
2. Set up a coding-agent CLI with an LLM provider
3. Use the SDK to create a workforce with 2-10 agents
4. Run a task on your workforce and verify results
5. Sync to the cloud dashboard and publish to the marketplace
6. Set your price

---

## Prerequisites

- Docker 24+ with Compose v2
- Python >= 3.10 or Node.js >= 18
- An LLM provider API key (OpenRouter recommended — get a key at [openrouter.ai/keys](https://openrouter.ai/keys))

---

## Phase 1 — Local backend

Start the backend container on your machine. All agent execution, LLM
calls, and data storage happen here.

```bash
# Pull the compose file
curl -fLO https://raw.githubusercontent.com/NavaiaSolutions/NavaiaForge/main/docker-compose.dist.yml

# Create your .env (fill in your license token and a strong password)
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
NEXT_PUBLIC_API_URL=http://localhost:8001
NEXT_PUBLIC_WS_URL=ws://localhost:8001
SECRET_KEY=$(openssl rand -hex 32)
EOF

# Start
docker compose -f docker-compose.dist.yml up -d

# Verify
curl http://localhost:8001/health
```

Your local backend: `http://localhost:8001`
Your local dashboard: `http://localhost:3030`

---

## Phase 2 — Agent runtime

The backend orchestrates agents but does not embed an LLM. It delegates
model execution to a coding-agent CLI on your machine. You need one of
these installed and authenticated.

### Recommended: Navaia Code + OpenRouter

```bash
# Install Navaia Code
navaia-code --version

# Authenticate with your OpenRouter API key
export OPENROUTER_API_KEY=sk-or-v1-your-key
```

You will create workforces with `runtime_mode="navaia_code"`.

### Alternative: Claude Code (Anthropic)

```bash
claude --version      # install: https://www.anthropic.com/claude-code
claude login          # uses your Anthropic subscription or API key
```

You will create workforces with `runtime_mode="claude_max"`.

---

## Phase 3 — Install the SDK and get your local API key

```bash
pip install navaia-forge
```

Generate an API key for your local backend. Either:

- Open `http://localhost:3030`, log in, go to **Settings > API Keys**, generate a key.
- Or use the SDK:
  ```python
  from navaia_forge import NavaiaForgeClient

  client = NavaiaForgeClient(base_url="http://localhost:8001")
  pair = client.auth.login(email="you@example.com", password="...")
  authed = NavaiaForgeClient(base_url="http://localhost:8001", api_key=pair.access_token)
  key = authed.auth.create_key("assessment-key")
  print(key.api_key)   # nf_... — store this, shown once
  ```

---

## Phase 4 — Build your workforce

Create a workforce with a minimum of **2 agents** and a maximum of
**10 agents**. The workforce should solve a real problem. You can:

- **Design your own** — pick any domain (sales, research, support, DevOps, content, etc.)
- **Adapt a prior project** — bring an agent solution you have built before and restructure it as a NavaiaForge workforce
- **Adapt something you find online** — find a compelling multi-agent setup and recreate it here using the SDK

The workforce must be **reasonable and functional** — it should produce
useful output when given a task.

### Example: a two-agent research team

```python
from navaia_forge import NavaiaForgeClient

local = NavaiaForgeClient(
    base_url="http://localhost:8001",
    api_key="nf_...",               # your local key from Phase 3
)

# Create the workforce
wf = local.workforces.create(
    name="Research Team",
    runtime_mode="navaia_code",     # or "claude_max"
)

# Add agents (minimum 2, maximum 10)
researcher = local.agents.create(
    workforce_id=wf.id,
    name="Researcher",
    role="research",
    instructions="Find and summarize information on the given topic. "
                 "Provide sources and key findings.",
    model_provider="openrouter",    # or "anthropic"
    model_name="anthropic/claude-sonnet-4-20250514",
)

writer = local.agents.create(
    workforce_id=wf.id,
    name="Writer",
    role="writer",
    instructions="Take the researcher's findings and produce a clear, "
                 "well-structured brief. Keep it under 500 words.",
    model_provider="openrouter",
    model_name="anthropic/claude-sonnet-4-20250514",
)

# Connect them: researcher -> writer
local.workforces.edges.create(
    workforce_id=wf.id,
    source_agent_id=researcher.id,
    target_agent_id=writer.id,
)

# Run a task
task = local.tasks.create(
    workforce_id=wf.id,
    title="Survey recent advances in multi-agent AI systems",
)
final = local.tasks.wait_for_completion(task.id)
print(final.status, final.result)
```

You are not limited to this structure. Use as many agents and edges as
your use case requires (within the 2-10 agent range).

---

## Phase 5 — Verify results

Confirm your workforce works:

1. **From the SDK** — print the completed task's `status` and `result`.
2. **From the local dashboard** — open `http://localhost:3030` and find
   your workforce and its completed task in the UI.

Both should show the same results.

---

## Phase 6 — Connect to the cloud and publish

### 6a. Get a cloud API key

1. Go to [fareegi.navaia.sa](https://fareegi.navaia.sa)
2. **Sign up** or **log in**
3. Go to **Settings > API Keys**
4. Generate a key — this is your cloud API key

### 6b. Sync your workforce to the cloud

```python
import os
from navaia_forge import NavaiaForgeClient

# Local backend (where execution happened)
local = NavaiaForgeClient(
    base_url="http://localhost:8001",
    api_key="nf_local_...",
)

# Cloud dashboard (display + marketplace)
cloud = NavaiaForgeClient(
    base_url="https://fareegi.navaia.sa",
    api_key="nf_cloud_...",
)

# Push your workforce to the cloud
result = local.sync.push(wf.id, remote=cloud)
print(f"Synced: {result.action}")
```

### 6c. Publish to the marketplace

```python
cloud.workforces.publish(
    result.workforce_id,
    tagline="A concise description of what your workforce does",
    category="research",           # choose an appropriate category
    price_cents=0,                 # 0 = free, or set your price in cents
    currency="SAR",                # SAR (default) or USD
)
```

Once published, your workforce enters a moderation queue. After the
Navaia team verifies it, it becomes visible in the marketplace.

---

## Assessment complete

When your workforce is published to the marketplace, the assessment is
done. To summarize, you should have:

- [ ] A running local backend
- [ ] A configured agent CLI (Navaia Code or Claude Code) with an LLM provider
- [ ] A workforce with 2-10 agents, created via the SDK
- [ ] A completed task demonstrating the workforce works
- [ ] Results visible in both the SDK output and the local dashboard
- [ ] The workforce synced to `fareegi.navaia.sa`
- [ ] The workforce published to the marketplace

---

## Earning from your workforce

You can set a price when you publish (`price_cents`). When another user
wants to install your workforce:

- **During the early access period** — the Navaia team will reach out to
  you to confirm the payment and deliver it manually.
- **After your workforce is verified** — you provide your bank account
  details and purchases are transferred to you automatically.

Free workforces (`price_cents=0`) are installable immediately by anyone.

---

## Two SDK clients — why?

Throughout the assessment you use **two API keys** pointed at **two
different servers**:

| Client | Base URL | Purpose |
|--------|----------|---------|
| `local` | `http://localhost:8001` | Your backend — all execution happens here |
| `cloud` | `https://fareegi.navaia.sa` | Display layer — marketplace, dashboard, sharing |

The local backend runs your agents and stores your data. The cloud is
where you sync results for visibility and publish to the marketplace.

---

## Reference

- Full setup walkthrough: [`SETUP.md`](./SETUP.md)
- Example scripts: [`examples/python/`](./examples/python/)
- SDK README: [`README.md`](./README.md)

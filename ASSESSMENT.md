# NavaiaForge SDK Assessment

Build a workforce, run it, and publish it to the marketplace.

---

## What you will do

1. Run the NavaiaForge backend locally (Docker)
2. Install the SDK and get your API keys
3. Create a workforce with 2-10 agents
4. Run tasks and chat with your agents
5. Sync to the cloud and publish to the marketplace

---

## Prerequisites

- Docker 24+ with Compose v2
- Python >= 3.10
- An OpenRouter API key with credits loaded ([openrouter.ai/keys](https://openrouter.ai/keys))

---

## Phase 1 — Run the backend

Start the backend container on your machine. All agent execution, LLM
calls, and data storage happen here.

```bash
# The compose file is included in this repository
# If you cloned the SDK repo, it's already at docker-compose.dist.yml
# Otherwise, download it:
curl -fLO https://raw.githubusercontent.com/NavaiaSolutions/navaia-forge-sdk/main/docker-compose.dist.yml

# Create your .env
cp .env.example .env
# Edit .env — set your OPENROUTER_API_KEY and POSTGRES_PASSWORD

# Start
docker compose -f docker-compose.dist.yml up -d

# Wait for all services to be healthy (~30 seconds), then run database setup
docker exec navaia-forge-api python -c "
import asyncio, app.auth.models, app.auth.api_key_models, app.hosting.models
import app.agents.models, app.workforces.models, app.tasks.models
import app.conversations.models, app.knowledge.models, app.integrations.models
import app.observability.models, app.templates.models, app.ratings.models
import app.sync.models, app.sync.instance
from app.agents.models import Base; from app.deps import engine
async def s():
    async with engine.begin() as c: await c.run_sync(Base.metadata.create_all)
    print('Database ready')
asyncio.run(s())
"

# Verify
curl http://localhost:8001/health
```

> **Windows users:** the `.env` block above uses bash syntax. On
> PowerShell or CMD, create the `.env` file manually in a text editor
> with the same key=value pairs. For `SECRET_KEY`, generate a random
> value with:
> ```
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

Your local backend: `http://localhost:8001`

The backend uses your `OPENROUTER_API_KEY` for both chat and task
execution. You pay OpenRouter directly — NavaiaForge never touches
your model credentials.

---

## Phase 2 — Install the SDK and get your API key

```bash
pip install navaia-forge
```

### Create an account and API key

**Via the SDK:**

```python
from navaia_forge import NavaiaForgeClient

client = NavaiaForgeClient(base_url="http://localhost:8001")

# Register (first time only — use login() after)
pair = client.auth.register(
    name="Your Name",
    email="you@example.com",
    password="your-password",
)

# Create a long-lived API key
authed = NavaiaForgeClient(
    base_url="http://localhost:8001",
    api_key=pair.access_token,
)
key = authed.auth.create_key("my-key")
print(key.api_key)   # nf_... — store this, shown once
```

---

## Phase 3 — Build your workforce

Create a workforce with a minimum of **2 agents** and a maximum of
**10 agents**. The workforce should solve a real problem. You can:

- **Design your own** — pick any domain (sales, research, support,
  DevOps, content, etc.)
- **Adapt a prior project** — bring an agent solution you have built
  before and restructure it as a NavaiaForge workforce
- **Adapt something you find online** — find a compelling multi-agent
  setup and recreate it here using the SDK

The workforce must be **reasonable and functional** — it should produce
useful output when given a task.

### Example: a two-agent research team

```python
from navaia_forge import NavaiaForgeClient

local = NavaiaForgeClient(
    base_url="http://localhost:8001",
    api_key="nf_...",
)

# Create the workforce
wf = local.workforces.create(
    name="Research Team",
    runtime_mode="navaia_code",
)

# Add agents (minimum 2, maximum 10)
researcher = local.agents.create(
    workforce_id=wf.id,
    name="Researcher",
    role="research",
    instructions="Find and summarize information on the given topic. "
                 "Provide sources and key findings.",
    model_provider="openrouter",
    model_name="anthropic/claude-sonnet-4",
)

writer = local.agents.create(
    workforce_id=wf.id,
    name="Writer",
    role="writer",
    instructions="Take the researcher's findings and produce a clear, "
                 "well-structured brief. Keep it under 500 words.",
    model_provider="openrouter",
    model_name="anthropic/claude-sonnet-4",
)

# Connect them: researcher -> writer
local.workforces.edges.create(
    workforce_id=wf.id,
    source_agent_id=researcher.id,
    target_agent_id=writer.id,
)
```

> **Important:** use the full OpenRouter model ID (e.g.
> `anthropic/claude-sonnet-4`, not just `sonnet`). You can browse
> available models at [openrouter.ai/models](https://openrouter.ai/models).

You are not limited to this structure. Use as many agents and edges as
your use case requires (within the 2-10 agent range).

---

## Phase 4 — Run and verify

### Run a task

```python
task = local.tasks.create(
    workforce_id=wf.id,
    title="Survey recent advances in multi-agent AI systems",
)
final = local.tasks.wait_for_completion(task.id)
print(final.status, final.result)
```

### Chat with your agents

You can also interact with the workforce via conversations:

```python
convo = local.conversations.create(workforce_id=wf.id)
msg = local.conversations.send_message(
    convo.id,
    "What are the top 3 trends in multi-agent AI right now?",
)

import time
time.sleep(10)

messages = local.conversations.messages(convo.id)
for m in messages:
    print(f"[{m.role}]: {m.content}")
```

---

## Phase 5 — Sync to cloud and publish

### 5a. Get a cloud API key

1. Go to [fareegi.navaia.sa](https://fareegi.navaia.sa)
2. Click **Get Started** to create an account (or **Sign In** if you
   have one)
3. Go to **Settings > Manage API keys**
4. Generate a key

### 5b. Sync your workforce to the cloud

```python
from navaia_forge import NavaiaForgeClient

local = NavaiaForgeClient(
    base_url="http://localhost:8001",
    api_key="nf_local_...",
)

cloud = NavaiaForgeClient(
    base_url="https://fareegi.navaia.sa",
    api_key="nf_cloud_...",
)

result = local.sync.push("your-workforce-id", remote=cloud)
print(f"Synced: {result.action}, cloud ID: {result.workforce_id}")
```

### 5c. Publish to the marketplace

```python
cloud.workforces.publish(
    result.workforce_id,
    tagline="A concise description of what your workforce does",
    category="research",
    price_cents=0,       # 0 = free, or set your price in cents
    currency="SAR",
)
```

Once published, your workforce enters a moderation queue. After the
Navaia team verifies it, it becomes visible in the marketplace.

---

## Assessment complete

When your workforce is published to the marketplace, the assessment is
done. You should have:

- [ ] A running local backend
- [ ] A workforce with 2-10 agents, created via the SDK
- [ ] At least one completed task or conversation showing the agents work
- [ ] The workforce synced to `fareegi.navaia.sa`
- [ ] The workforce published to the marketplace

---

## Earning from your workforce

You can set a price when you publish (`price_cents`). When another user
wants to buy your workforce:

- **During early access** — the Navaia team will reach out to you to
  confirm the payment and deliver it manually.
- **After verification** — you provide your bank account details and
  purchases are transferred to you automatically.

Free workforces (`price_cents=0`) are installable immediately by anyone.

---

## Two SDK clients — why?

You use two API keys pointed at two different servers:

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

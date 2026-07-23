# NavaiaForge LLM Runbook — WhatsApp (Baian) Templates & Telegram Bot

> **Give this whole file to your LLM at the START of the session.** Then tell it:
> *"Do Phase 1"* (get a WhatsApp template approved) or *"Do Phase 2"* (install the
> Telegram bot). This file is generic — it works for ANY NavaiaForge workforce.
> It assumes nothing about your agents, verticals, or templates.

---

## 0. INSTRUCTIONS TO THE LLM (read first, obey exactly)

You are an operator working on a **NavaiaForge** workforce. Follow this runbook **literally**.

- **Do not improvise API shapes.** If a value (WABA id, token, workforce id, base URL) is
  unknown, **STOP and ask the human for it** — never invent it.
- **Do not "fix", reformat, or retry-with-changes** a JSON payload after a failure. Failures
  here are almost always a *rule* violation, not a formatting bug — find the rule in §1.2 / §1.7.
- **Introspect real tools before calling them.** Endpoint versions and env-var names vary per
  deployment. List the integration's available tools/fields instead of hardcoding.
- **Verify every step** with the check described before moving on. Do not report success you
  did not observe. If a step fails twice, STOP and report the exact error to the human.
- Keep shell/tool calls **short and single-purpose** (one command, one file). Long multi-line
  calls fail more often on these runtimes.

### Placeholders used below (replace before running)
| Placeholder | Meaning | Where to get it |
|---|---|---|
| `<API_KEY>` | Your NavaiaForge workforce API key | Your NavaiaForge dashboard → API Keys |
| `<BASE_URL>` | Your backend API URL | Self-host: `http://localhost:8001`. Managed: the URL your provider gave you |
| `<WORKFORCE_ID>` | The workforce's UUID | Dashboard, or `client.workforces.list()` |
| `<AGENT_ID>` | An agent that can use the integration | `client.agents.list(workforce_id=<WORKFORCE_ID>)` |
| `<API_VERSION>` | Meta Graph API version, e.g. `v24.0` | Ask human / use current |
| `<WABA_ID>` / `<META_TOKEN>` | WhatsApp Business Account id + token | Held inside the Baian integration's config/env — see §1.3 |

### One-time setup (Python)
```bash
python -m venv .venv
.venv/Scripts/pip install navaia-forge   # SDK client (import name: navaia_forge)
```
```python
from navaia_forge import NavaiaForgeClient
client = NavaiaForgeClient(api_key="<API_KEY>", base_url="<BASE_URL>")
```

---

# PHASE 1 — Get a WhatsApp (Baian) template APPROVED

**Goal:** submit a WhatsApp message template so Meta APPROVES it, so the workforce can send
first-contact messages. (First contact **requires** an approved template; free text is only
allowed inside the 24-hour window *after* the customer replies.)

## 1.1 What you need first (collect these, then proceed)
1. The **Baian (WhatsApp) integration is CONNECTED** to the workforce. Confirm with
   `client.integrations.list(workforce_id=<WORKFORCE_ID>)` — look for a `baian`/whatsapp entry
   with status `active`. If missing, STOP: the human must connect it.
2. An **agent id** in the workforce that is allowed to use Baian (any agent with the
   integration in its tool set). Get it from `client.agents.list(...)`.
3. Confirm you can reach Baian's WABA id + Meta token — **do not print their values**, just
   confirm they exist (§1.3).

## 1.2 The Meta rules that cause ~90% of rejections (MEMORIZE)
Most "INVALID_FORMAT" rejections are one of these. Build the payload to satisfy ALL of them:

1. **No leading or trailing variable.** The BODY text must **not start or end with `{{n}}`**.
   Put fixed text before `{{1}}` and after the last `{{n}}`. *(Meta `error_subcode 2388299`.)*
2. **Every variable needs an example.** Include `example.body_text` — an array of sample
   values, one per variable, in order. Missing it → `INVALID_FORMAT`.
3. **Variables are sequential with no gaps:** `{{1}}, {{2}}, {{3}}` — never skip a number,
   never reuse.
4. **30-day name lock.** A template `name`+`language` you **deleted** cannot be re-created for
   ~30 days *(`error_subcode 2388023`)*. If you hit this, **use a new name** (append `_v2`).
5. **`name`** = lowercase letters, digits, underscores only. **`category`** = `MARKETING`
   (outreach), `UTILITY`, or `AUTHENTICATION`. **`language`** = an exact code like `ar`,
   `en_US` — and you must send with the SAME language later.

## 1.3 The RELIABLE submission method (direct Graph API via a tightly-scoped task)
Baian's own `create_template` tool has proven **unreliable** (agents mangle it). The robust
path is to have a Baian-capable agent make **exactly one** direct Graph API POST, tightly
constrained so the agent runtime cannot "help." The WABA id and Meta token live in Baian's
environment (commonly env vars like `NF_BAIAN_WABA_ID` and `NF_BAIAN_META_TOKEN` — **have the
agent read them from Baian's configured environment; do not hardcode or print them**).

The Graph API call the agent must make:
```
POST https://graph.facebook.com/<API_VERSION>/<WABA_ID>/message_templates
Authorization: Bearer <META_TOKEN>
Content-Type: application/json
```

## 1.4 The payload (fill placeholders; keep the shape EXACT)
```json
{
  "name": "your_template_name_here",
  "category": "MARKETING",
  "language": "ar",
  "components": [
    {
      "type": "BODY",
      "text": "Fixed opening text {{1}}, then more fixed text. {{2}} Fixed closing text after the last variable.",
      "example": { "body_text": [["Sample for {{1}}", "Sample for {{2}}"]] }
    }
  ]
}
```
Rules recap applied above: fixed text wraps the variables (rule 1), `example.body_text` present
(rule 2), variables sequential (rule 3). Add optional `HEADER`/`FOOTER`/`BUTTONS` components
only if you know their rules.

## 1.5 Submit it (create a tightly-scoped task)
Give the agent a description that **forbids improvisation** — this is what makes it reliable:
```python
PAYLOAD = '''<paste the exact JSON from §1.4 here, unchanged>'''
desc = f"""Your ONLY job is to make ONE HTTP POST and report the response verbatim. Nothing else.
Do NOT use Baian's create_template tool. Do NOT check if it exists. Do NOT modify the JSON.
Do NOT retry with a different format. Do NOT add/remove/rename fields. Do NOT send any message.

Steps:
1. Read the WhatsApp Business Account id and token from Baian's configured environment
   (do not print them).
2. Make exactly ONE request:
   POST https://graph.facebook.com/<API_VERSION>/<WABA_ID>/message_templates
   Authorization: Bearer <META_TOKEN>
   Content-Type: application/json
   Body (send EXACTLY this, character for character):
{PAYLOAD}
3. Report the HTTP status code and the FULL response body verbatim. Then STOP."""

t = client.tasks.create("<WORKFORCE_ID>", "Submit WA template", description=desc,
                        agent_id="<AGENT_ID>", metadata={"action": "create_template"})
# poll:
import time
while True:
    t = client.tasks.get(t.id)
    s = str(t.status).lower()
    if "waiting_plan" in s:
        client.tasks.approve(t.id)          # let it proceed
    elif s in ("done","failed","cancelled","waiting_question","waiting_blocked"):
        break
    time.sleep(6)
print(t.status, t.result)
```
**Success looks like:** HTTP `200` with a JSON body containing an `id` and
`"status": "PENDING"` (or `APPROVED`). Anything with `"error"` → go to §1.7.

## 1.6 Check approval status (poll until APPROVED)
Approval is usually **minutes**. Check by listing templates via Baian's `list_templates` tool,
or a direct `GET https://graph.facebook.com/<API_VERSION>/<WABA_ID>/message_templates?name=<name>`
(same tightly-scoped-task pattern). Statuses: `PENDING` → `APPROVED` or `REJECTED` (with a
reason). **After approval, verify the approved BODY text matches what you submitted** — Meta can
shorten/alter it, and you must send the exact approved shape.

## 1.7 Error → fix table
| Symptom | Cause | Fix |
|---|---|---|
| `INVALID_FORMAT`, subcode `2388299` | BODY starts or ends with `{{n}}` | Wrap variables in fixed text (rule 1) |
| `INVALID_FORMAT` (no subcode) | Missing `example.body_text` | Add an example value per variable (rule 2) |
| subcode `2388023` (name taken) | 30-day lock on a deleted name | Use a new `name` (append `_v2`) |
| Variables not applied / count mismatch at send | Gaps or wrong order in `{{n}}` | Renumber sequentially (rule 3) |
| `190` / auth error | Wrong/expired Meta token | Human refreshes Baian's Meta token |
| Rejected: category | Wrong `category` for content | Outreach = `MARKETING` |

## 1.8 Send with an approved template (first contact)
Use Baian's `send_template` with the **approved** template `name`, the same `language`, the
recipient in E.164 (`+9665XXXXXXXX`), and the body variables **in order**. First contact **must**
use an approved template. After the customer replies, you get a 24-hour window for free text.

---

# PHASE 2 — Install the Telegram bot on YOUR workforce

**Goal:** let you drive the workforce (create tasks, ask agents, get status) from Telegram, and
receive the agents' replies + `waiting_plan`/`waiting_question` prompts in a chat.

## 2.1 How it launches (understand this or you'll waste hours)
The Telegram bot ships **inside the backend image** already. It is launched **only at backend
startup, from three environment variables** — NOT from the DB / integration config. Setting the
Telegram integration's `config_json` via API does **nothing**; only env + a restart works.
```
TELEGRAM_BOT_TOKEN=<from BotFather>
TELEGRAM_CHAT_ID=<your chat or group id>
TELEGRAM_WORKFORCE_ID=<WORKFORCE_ID>
```

## 2.2 Step 1 — create the bot
In Telegram, message **@BotFather** → send `/newbot` → follow prompts → copy the **bot token**
(looks like `123456789:AA...`). Keep it secret.

## 2.3 Step 2 — get your chat id
- **Personal chat:** message **@userinfobot**; it replies with your numeric id. (Or: send any
  message to YOUR new bot, then open
  `https://api.telegram.org/bot<TOKEN>/getUpdates` and read `message.chat.id`.)
- **Team group:** add your bot to the group, send a message, open the same `getUpdates` URL,
  and read the group's `chat.id` (it's **negative**, e.g. `-100...`).
- Everyone who should use/see the bot must be in that chat.

## 2.4 Step 3 — set the 3 env vars + recreate the API
> A plain `restart` does NOT reload env files — you must **recreate** the container.

- **Self-hosted (you run the Docker stack):** put the 3 vars in the `.env` that your
  `docker-compose` loads (the one referenced by `env_file:`), then:
  ```bash
  docker compose up -d --force-recreate <api-service-name>
  ```
- **Managed backend (a provider hosts it):** you cannot set host env or restart. **Send the
  provider this request:** "Set `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
  `TELEGRAM_WORKFORCE_ID=<WORKFORCE_ID>` on the backend serving our workforce and recreate the
  API container." (Share the token/chat id securely, not in a public channel.)

## 2.5 Step 4 — verify
- Backend logs show: `Telegram bot started (chat=...)`.
- In Telegram, send **`/help`** to the bot — it should reply.
- If silent: (a) wrong `chat_id` (the bot ignores every chat except the configured one),
  (b) env not loaded (you restarted instead of recreated), (c) two processes polling the same
  token (see §2.7).

## 2.6 Adapt to YOUR workforce (IMPORTANT — capability-specific behavior)
The shipped inbound bot has **hardcoded agent-name assumptions**:
- `/task <text>` and **plain text** → dispatched to an agent named **`Ahmed`** (the orchestrator).
- `/report` → dispatched to an agent named **`Rashid`**.
- `/ask <AgentName> <question>` → **fuzzy-matches ANY agent name** in your workforce.

So, to fit your workforce:
- If your orchestrator is **not** named `Ahmed`, either (a) name an orchestrator agent `Ahmed`,
  or (b) tell your users to use `/ask <your-orchestrator> ...` instead of `/task`.
- If you have no `Rashid`, `/report` won't route — use `/ask <your-analyst> ...`.
- Confirm your agent names first: `client.agents.list(workforce_id=<WORKFORCE_ID>)`.

Available commands: `/task`, `/ask <agent> <q>`, `/status`, `/report`, `/schedules`,
`/pause <name>`, `/resume <name>`, `/help`.

## 2.7 Known limitations (tell the human up front)
- **One bot per backend process.** The 3 env vars are process-global — a backend runs exactly
  ONE bot for ONE workforce. On a **shared/multi-tenant** backend you cannot give each workforce
  its own Telegram via env; that needs a dedicated backend instance or a provider feature.
- **Only one poller per bot token.** Never run two things polling the same token (e.g. a local
  script AND the backend) — they steal each other's updates. Stop one first.
- **No built-in approval command.** The bot **pushes** `waiting_plan`/`waiting_question` to the
  chat, but the shipped inbound bot has **no `/approve`** and no way to route your reply back to
  a waiting task. If you need human-in-the-loop *approval from Telegram*, that's a custom bridge
  or a provider feature — the stock bot only notifies.

---

## Final checklist
**Phase 1 (template):** integration connected ▢ · payload obeys all §1.2 rules ▢ · submitted via
tightly-scoped task ▢ · status `APPROVED` ▢ · approved body verified verbatim ▢
**Phase 2 (Telegram):** bot created ▢ · chat id obtained ▢ · 3 env vars set ▢ · container
**recreated** (not just restarted) ▢ · `/help` replies ▢ · agent-name routing adapted to your
workforce ▢

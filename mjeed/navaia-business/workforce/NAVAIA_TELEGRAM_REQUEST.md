# Request to Navaia — always-on Telegram control for our workforce (in-Kingdom, PDPL)

**Goal:** run our Telegram control/approval bot 24/7 so we can start and **approve** outreach
from a phone with the laptop closed. It handles lead **personal data** (names, phones), so under
**PDPL** it must run **in-Kingdom**, not on a foreign host.

**Workforce id:** `131bb52f-e5eb-44ad-8134-03dc6908b485`

---

## The ask — enable the native in-image bot on fareegi

The backend image already ships a Telegram bot (`app/integrations/telegram_bot.py` +
`plugins/telegram.py`), launched from env at API startup (`app/main.py`). It runs on **your
in-Kingdom infra** — no foreign host and no separate container from us. On the backend process
serving our workforce, set:

```
TELEGRAM_BOT_TOKEN=<sent securely>
TELEGRAM_CHAT_ID=<sent securely>
TELEGRAM_WORKFORCE_ID=131bb52f-e5eb-44ad-8134-03dc6908b485
```

then recreate the API so it reloads env (`docker compose up -d --force-recreate <api-service>`).
**Verify:** logs show `Telegram bot started (chat=...)`, and `/help` replies.

This gives always-on command control from the phone: `/task /ask /status /report /pause /resume`.

---

## Two gaps to close with it

1. **HITL approval isn't wired *in the native bot*.** To be clear, there are **two separate bots**:

   - **Our local bot** (`scripts/telegram_workforce_bot.py`, runs on the laptop) — already does full
     HITL: approve / answer / reject, and re-run for blocked tasks. **This is working today.** But it
     only runs while the laptop is on, so it is **not always-on**.
   - **The native in-image bot** (ships inside your backend image, the one this request asks you to
     enable on fareegi for always-on) — is **command-only** (`/task /ask /status /report /pause
     /resume`) and has **no approve path**. Enabling it as-is gives always-on control **without**
     the ability to approve outreach sends from the phone.

   So the fix we applied on our side does **not** cover the native bot — please add approve / reject /
   answer to it. The backend API already supports it: `POST /tasks/{id}/approve` (requires a JSON
   body — a bodyless call returns 422; a `waiting_blocked` task returns 400 and must be re-run) and
   the matching reject path. Our local bot is a working reference implementation you can mirror.

   **Include the TEST/LIVE send toggle.** Our local bot lets the operator flip outreach sends between
   **TEST** (route the WhatsApp to the operator's own number, `MY_PHONE`) and **LIVE** (send to the
   real lead) **from Telegram at runtime** — a `🔀 Send mode` button and a `/mode` command, with a
   confirm step before going LIVE — **no restart**. Please mirror this in the native bot so we can
   smoke-test a real send end-to-end and then go live without redeploying. The starting mode can be an
   env default (e.g. `TELEGRAM_SEND_MODE=test|live`), but the switch itself must be in-chat.

2. **Per-workforce provisioning on shared infra.** The open backend launches **one bot per backend
   process** (process-global env), and the plugin registry does **not** load Telegram config from
   the DB — only from env at startup. If fareegi is **shared multi-tenant**, setting one customer's
   token via env makes it the *only* Telegram on that process. **How do you provision per-workforce
   Telegram on shared infra** — a dedicated instance, a managed per-workforce mechanism, or is it a
   feature request?

We'll send the bot token + chat id over a secure channel — not in this doc.

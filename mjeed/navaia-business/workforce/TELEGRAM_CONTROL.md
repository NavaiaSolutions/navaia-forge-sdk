# Telegram control of the NAVAIA workforce — full capability review

> **Verified fresh 2026-07-13** against the live bot and the live cloud API
> (`fareegi.navaia.sa`, workforce `131bb52f-…`). This is the authoritative map
> of what you can do from Telegram, how it is wired, and the gaps to close for
> true "assign tasks + full control from my phone."

---

## 1. What is live right now (verified)

| Thing | State (checked 2026-07-13) |
|-------|----------------------------|
| Telegram bot | **@NAV_BIZNESSbot** ("BIZNESS"). Long-polling (`getUpdates`), **no webhook**. Privacy mode on. No command menu registered (`setMyCommands` empty). |
| Operator chat | `TELEGRAM_CHAT_ID = 7172651886` — the bot only listens to / talks to this one chat. |
| Control code | `scripts/telegram_workforce_bot.py` — a local process bridging Telegram ⇄ the cloud API. This is the real control surface. |
| Cloud APIs it drives | `agents.list` (7 agents), `tasks` (create/get/list/approve/reject — 50 tasks, one currently `waiting_question`), `conversations` (create/list/messages/send_message — 7 convs). All responding. |
| Runtime | `runtime_mode = navaia_code` → tasks you assign run on **Kimi K2.6** (per-agent `model_name`). |

There are **two possible Telegram implementations** — you are using the first:

- **A. Custom bot** (`scripts/telegram_workforce_bot.py`) — rich: task assignment, HITL
  approve/answer/reject, agent chat, task browser, send approval. Runs as its own process.
- **B. Native in-image bot** — ships inside the backend Docker image, started from host env
  vars at API startup. Command-only (`/task /ask /status /report /pause /resume`), **no HITL
  approve/answer, no chat**. It lives only inside the managed backend image (not inspectable or
  runnable by us), and enabling it needs Navaia to set env on fareegi. Not recommended given A
  is strictly more capable.

**One-poller rule:** exactly one process may poll a bot token. If the native bot (B) were ever
enabled on the same token, it would collide with A. Pick one.

---

## 2. Full capability map of the custom bot (A)

Everything below is reachable by a **button** (tap `/menu`) or a **typed command**. Commands win
even inside a mode.

### Assign work to the workforce
| Action | How | What happens |
|--------|-----|--------------|
| Give the GM a job / pipeline | `/task <text>`, plain text, or 🆕 **New task** | Creates a task for **Ahmed** (orchestrator). Ahmed can decompose and delegate to the other agents. |
| Ask one specific agent | `/ask <Agent> <question>` or 👥 **Ask an agent** | One-shot task to that agent (Tariq, Lina, Fahad, Nora, Rashid, Ghida). |
| Daily ops summary | `/report` or 📈 **Daily report** | Task to **Rashid** → 5-line wins/blockers summary. |

### Converse (multi-turn)
| Action | How | What happens |
|--------|-----|--------------|
| Open a live chat with an agent | `/chat <Agent>` or 💬 **Chat** | Real back-and-forth via the **conversations API**; `__team` routes through Ahmed. `/menu` exits. |
| Resume an earlier chat | `/chats` | Lists recent conversations with last-message preview + msg count; tap to resume. |

### Monitor
| Action | How | What happens |
|--------|-----|--------------|
| Recent tasks | `/status` or 📊 **Status** | Last ~10 tasks with status icons. |
| Browse + read outputs | `/tasks` or 🗂 **Tasks** | Running / completed / all; tap a task to read its **full output** (paged). |

### Human-in-the-loop approvals — the core control
| Action | How | What happens |
|--------|-----|--------------|
| See everything waiting on you | `/approvals` or ⏳ **Approvals** | All tasks in `waiting_plan` / `waiting_question` / `waiting_blocked`. |
| Approve a plan / unblock | ✅ **Approve** | `tasks.approve` → agent resumes. |
| Answer a question | ✍️ **Answer** → type reply | `POST /tasks/{id}/approve {"response": <text>}` → the answer reaches the agent (a bare approve carries no text, so the agent would just re-ask — this is why questions get **Answer**, not Approve). |
| Reject / cancel | ❌ **Reject** | `tasks.reject(reason)` → task cancelled. |

Nothing proceeds past a pause until you decide. The watcher polls every ~8s and pushes an
approval card the moment a task pauses.

**Fixed 2026-07-13 (from a live failure):** the backend `/tasks/{id}/approve` endpoint **requires a
JSON body** — the SDK's bodyless `tasks.approve()` returned **HTTP 422**, so the ✅ Approve button
was broken for every waiting task. The bot now always POSTs a body. Also, a **`waiting_blocked`**
task can't be approved or answered (backend returns **400** — only `waiting_plan`/`waiting_question`
are approvable), so a blocker now shows **🔁 Re-run** (cancel + re-create the task once the blocking
dependency is fixed) instead of a dead Approve/Answer.

### Outreach sends
| Action | How | What happens |
|--------|-----|--------------|
| Approve WhatsApp Touch-1 | `/send` or 📣 **Approve outreach sends** | Per-lead card: company + sector + website + **masked phone** + a Google verify link + the rendered Arabic message, with ✅ Approve / ⏭️ Skip. Approve → a Baian send task (via **Tariq**, cloud-only) → on success sets CRM `leadStatus = WhatsApped`. |

**PDPL note:** only a masked phone (`+966•••••577`) and company name go to Telegram; the full
number travels only to the cloud/Baian send task, never into the chat.

---

## 3. Gaps to close for "full control from my phone"

1. **Always-on hosting (the big one).** The custom bot is a **local process** — it dies when the
   laptop sleeps. For 24/7 control the container must run somewhere. Because it touches lead
   personal data, PDPL points to an **in-Kingdom** host. Deploy artifacts are ready in
   `deploy/telegram-bot/` (Dockerfile, docker-compose, systemd unit). The pending ask to Navaia is
   `NAVAIA_TELEGRAM_REQUEST.md` (Option 1 = run our container in-Kingdom). Until then: run it
   locally with `python scripts/telegram_workforce_bot.py` (stop any other poller first).
2. **`/send` is a fixed pilot batch.** It currently offers only 3 hard-coded Real-Estate leads. To
   send to any lead today you go `/task → Ahmed → Tariq` (which does the per-lead personalization).
   A generalized "approve any pending send from the CRM" card is a worthwhile enhancement.
3. **No scheduler control.** The custom bot has no `/schedules /pause /resume`. If you want to
   pause/resume the workforce or view the pipeline scheduler from Telegram, that needs adding.
4. **No Telegram command menu.** Commands work but aren't registered via `setMyCommands`, so they
   don't autocomplete in the Telegram UI. Quick win.
5. **Single operator.** Locked to one `chat_id`. Fine for now; note it if others need access.
6. **Cloud Telegram integration duplicate is irrelevant to A** (the custom bot polls the token
   directly and ignores the DB integration record) — but the stale duplicate matters if you ever
   switch to the native bot (B). See `07_open_items_and_status.md` → Blocked.

---

## 4. Recommendation

- The custom bot **already delivers "assign tasks + full control"**: assign to Ahmed or any agent,
  chat, monitor, approve/answer/reject, and approve sends — all from the phone.
- To make it your **always-on** controller, the one real dependency is hosting: push Navaia on
  `NAVAIA_TELEGRAM_REQUEST.md` Option 1 (in-Kingdom container). That is the permanent version.
- Optional upgrades, in priority order: (a) generalize `/send` to any CRM lead; (b) add
  `/schedules /pause /resume`; (c) register `setMyCommands` for autocomplete.

---

## 5. Run it now (local stopgap)

```bash
# ensure no other process polls the token (stop the local backend bot if running)
python scripts/telegram_workforce_bot.py            # starts LIVE — sends to real leads on approval
python scripts/telegram_workforce_bot.py --to-me    # starts in TEST — send approvals go to MY_PHONE
```

TEST vs LIVE is a **runtime toggle** — flip it from Telegram itself (`🔀 Send mode` button or
`/mode`, with a confirm before going LIVE); no restart needed. `--to-me` only sets the starting mode.

Secrets are read from `.env`: `BUSINESS_NF`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `MY_PHONE`,
`TWENTY_TOKEN`. Nothing is hardcoded.

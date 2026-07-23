# Always-on Telegram bot — deploy

Runs `scripts/telegram_workforce_bot.py` 24/7 so you can drive + approve the **cloud**
workforce from your phone with the laptop closed. It's a thin, **stateless relay**: long-polls
Telegram, calls the cloud workforce API, holds no data at rest.

## PDPL — why this hosts in-Kingdom (decided 2026-07-13)

The bot handles **personal data** (lead names, phone numbers) from Twenty CRM and relays it to
Telegram + Baian. Under **PDPL** (SDAIA's *Regulation on Personal Data Transfer outside the
Kingdom*), processing Saudi personal data abroad is a regulated cross-border transfer — so
**free foreign VMs (Oracle/GCP/Fly US regions) are out**. Chosen posture:

- **Host on Navaia's own in-Kingdom infrastructure** (same trust boundary as the CRM/backend).
- **Data-minimization to Telegram:** approval cards drop the address and **mask the phone**
  (`+966•••••577`); the full number only travels to the cloud/Baian send task, never into the
  chat. (`_mask_phone` + `company_block` in the bot.)
- **Still to settle with your DPO:** Telegram itself is a foreign processor — company name +
  masked phone still leave the Kingdom via Telegram. Document/accept this in your PDPL record.

If you ever accept a foreign host, the artifacts below run unchanged — only the region differs.

## What Navaia runs (this image)

A container that needs only `navaia-forge` (public PyPI) + `httpx` plus the pipeline toolkit
(`nav_env.py`, `telegram_workforce_bot.py`, `pipeline_prep.py`, `submit_lead_batch.py`,
`lina_compose.py`, the template source `04_outreach_templates.md`, and a lead-pool snapshot).
Secrets are injected as **env vars**, never baked in (now incl. `SNOV_USER_ID/SECRET` for the
pipeline prep). See `NAVAIA_TELEGRAM_REQUEST.md` for the hand-off ask.

## 🚀 Fire the pipeline from your phone (laptop off)

The menu's **🚀 Fire pipeline** button runs the WHOLE loop without any other machine:

1. **📦 New lead batch** — picks the next unsubmitted scraped leads from the pool
   (volume copy, markers survive rebuilds), enriches emails via Snov, embeds the
   approved templates, and submits the task to Ahmed.
2. **📣 Outreach existing** — normalizes CRM fields, enriches missing emails, embeds
   the Not Contacted leads + templates, submits to Ahmed.
3. The **approval gate arrives in this chat** (✍️ Answer card) — approve, and the
   report follows here too. Start → approve → report, phone-only.

The laptop is only needed to REFILL the pool (browser scrape) and for prompt/doc
maintenance — see `workforce/playbooks/lead_pipeline.md`.

### Option A — Docker Compose (recommended)
From this folder on the in-Kingdom host:
```
cp .env.example .env      # fill BUSINESS_NF, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, MY_PHONE, TWENTY_TOKEN
chmod 600 .env
docker compose up -d --build
docker compose logs -f     # expect: Bot online. agents=[...]
```

### Option B — systemd (no Docker)
See the header of `navaia-tg-bot.service` for the full steps (venv + `EnvironmentFile` + enable).

## Critical: one poller per token
Telegram allows **one** process to long-poll a bot token. Before starting this, **stop the local
laptop bot** and any local `navaia-forge-api` that has `TELEGRAM_*` set — otherwise Telegram
returns `409 Conflict` and neither works. This cloud bot then becomes the single always-on poller.

## Test vs live
- Default command = **live** (a send-approval tap messages the real lead; you still approve each).
- For a safe smoke test, run with `--to-me` (routes send-approvals to `MY_PHONE`) — see the
  commented `command:` in `docker-compose.yml`.

## Verify
1. Logs show `Bot online. agents=[...]`.
2. The chat receives `🟢 NAVAIA workforce bot online.` with the menu.
3. `/status` replies; `💬 Chat` gets an agent reply; `⏳ Approvals` lists any waiting tasks.

## Files
- `Dockerfile` — the image (build context = repo root).
- `docker-compose.yml` — one-command run on any host.
- `navaia-tg-bot.service` — systemd unit for a no-Docker VM.
- `.env.example` — the 5 secrets to provide (copy to `.env`, never commit).

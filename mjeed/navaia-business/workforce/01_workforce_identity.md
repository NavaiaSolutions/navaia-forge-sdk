# 01 — Workforce Identity, Sync & Dashboard

> Workforce IDs, sync mechanism, and Fareegi dashboard integration.

---

## Purpose

Run the "NAVAIA Business" workforce fully locally (Docker stack) while keeping
it two-way synced to the Fareegi cloud (`fareegi.navaia.sa`) for monitoring via
the dashboard (outputs, knowledgebase, chats, scheduler/pipeline).

The workforce is a business-development team. The user is a BD intern learning
sales and inbound capture, so the workflow must be **customizable** and
**expandable** — new data sources, new agents, and new outreach channels should
be addable without re-architecting the whole thing.

---

## Workforce IDs

| Environment | Workforce ID |
|-------------|--------------|
| Local       | `8515d24a-6195-4a73-9cd3-37eb02f08693` |
| Cloud       | `131bb52f-e5eb-44ad-8134-03dc6908b485` |

Sync is bidirectional via `local.sync.push/pull(workforce_id, remote=cloud)`.
`origin_id` on every entity prevents duplication on round-trips.

---

## Fareegi Dashboard Integration

The cloud dashboard is the monitoring surface. Everything the workforce does
should be visible there:

| Dashboard surface | What lands here |
|-------------------|-----------------|
| **Outputs** | Lead lists, generated templates, sent emails, reports |
| **Knowledgebase** | CRM file (Phase 1), lead enrichment notes, context docs |
| **Chats** | GM conversations, agent-to-agent handoffs, user escalations |
| **Scheduler / Pipeline** | Automated outreach cadences, follow-ups, periodic lead-fetch runs |

Because sync is two-way, anything produced locally appears on cloud and any
task assigned on cloud flows down to local execution.

### Dashboard URLs

- **Cloud dashboard:** `https://fareegi.navaia.sa`
- **API base:** `https://fareegi.navaia.sa/api/v1`
- **Auth header:** `x-api-key: YOUR_API_KEY` (create one in Settings → API Keys)

### Integrations API (example)

```bash
curl -X POST https://fareegi.navaia.sa/api/v1/integrations \
  -H "x-api-key: YOUR_API_KEY" -H "Content-Type: application/json" \
  -d '{
        "workforce_id": "YOUR_WORKFORCE_ID",
        "plugin_name": "apollo",
        "config_json": { "api_key": "YOUR_APOLLO_KEY" }
      }'
```

Supported providers (see `10_integration_keys.md`):
- `hunter` → `{"api_key": "…"}`
- `snov` → `{"client_id": "…", "client_secret": "…"}`
- `twenty` → `{"api_key": "…"}` (base URL preset to `https://crm.navaia.sa`)
- `apollo` → `{"api_key": "…"}`

---

## Agents Summary (7 pre-built)

| Name   | Role              | Status | File |
|--------|-------------------|--------|------|
| Ahmed  | GM (orchestrator) | Active | `agents/ahmed_gm_orchestrator.md` |
| Tariq  | SDR / Lead Fetcher | Active | `agents/tariq_sdr_sender.md` |
| Lina   | Marketing — **writes** outreach copy | Active (content) | `agents/lina_marketing.md` |
| Ghida  | Creative          | Phased | `agents/ghida_creative.md` |
| Nora   | Finance          | Phased | `agents/nora_scorer.md` |
| Rashid | Strategy          | Phased | `agents/rashid_scraper.md` |
| Fahad  | Account Manager   | Phased | `agents/fahad_account_manager.md` |

Outreach is a **capability**, not an agent — Lina writes, Tariq sends. The channels are
wired via integrations owned by Tariq:
- **Email** — Snov.io campaign → connected **Zoho** mailbox (`ops@navaia.sa`)
- **WhatsApp** — **Baian** (Meta), **cloud-only** (secret lives only in cloud)

---

## Sender Identity

| Field | Value |
|-------|-------|
| **Name** | عبدالمجيد الوردي / Abdulmajeed Alwardi |
| **Role** | تطوير الأعمال / Business Development |
| **Company** | نڤايا / NAVAIA |
| **Phone** | `NAVAIA_CONTACT_PHONE` (see .env) |
| **cal.com** | https://cal.com/abdulmajeed-alwardi |
| **Email** | ops@navaia.sa |

---

## Future Expandability

- **More agents** — the user wants to explore additional agents together
  (e.g., inbound-lead-qualifier, meeting-scheduler, analytics agent).
- **More data sources** — Lead Fetcher's source list is editable.
- **Twenty CRM** — swap the file CRM for the API once the account is ready
  (already done).
- **Scheduler automation** — turn the happy path into a scheduled pipeline
  (e.g., weekly lead-fetch + outreach cadence) via the Fareegi scheduler.
- **Agent enhancements** — each agent's instructions/tools can be iteratively
  refined through the SDK without touching the backend image.
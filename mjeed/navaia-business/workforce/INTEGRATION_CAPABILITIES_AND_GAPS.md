# Integration Capabilities & Gaps — handoff for the Tech Team

> **Purpose:** hand the confirmed integration **limitations** to the tech team, and record
> the **full set of functions reachable** by this workforce. Verified live on 2026-07-08
> against the cloud workforce `131bb52f-e5eb-44ad-8134-03dc6908b485`.

---

## TL;DR — the two blocking gaps

Branded **email outreach cannot be sent from the workforce today**, for two reasons:

1. **`zoho_mail.send` is plain-text only.** The backend `zoho_smtp.py` uses
   `MIMEText(body, _charset="utf-8")` (defaults to `text/plain`) and exposes no HTML option.
   A test email with an HTML signature **arrived with the raw HTML tags visible**, not rendered.
2. **The Snov integration has no send/campaign functions** — only enrich/verify. So the
   documented "Snov → Zoho campaign" outreach path is **not wired**.

Net effect: no way to send a rendered, branded (HTML + signature) email from the workforce.
Everything else (WhatsApp, CRM, enrichment, verification, plain-text email) works.

---

## Part 1 — Full functions reachable by the workforce (toolbridge audit)

23 functions across 7 integrations. **Active** = keyed & usable now. **Needs key** = function
exists but the integration isn't connected.

| Integration | Status | Functions |
|-------------|--------|-----------|
| **Baian (WhatsApp)** | ✅ Active | `send_message` (free text, inside 24h window) · `send_template` (approved template / first contact) · `find_customer` · `create_template` (submit to Meta) · `list_templates` |
| **Zoho Mail** | ✅ Active | `zoho_mail.send` (SMTP send — **plain text only**, see gap #1) |
| **Snov.io** | ✅ Active | `domain_search` · `find_email` · `verify_email` — **enrich/verify only, NO send** (gap #2) |
| **Twenty CRM** | ✅ Active | `create_person` · `search_people` · `create_company` · `create_opportunity` |
| **NAVAIA CRM proxy** (over Twenty) | ✅ Active | `crm.list` · `crm.get` · `crm.create` · `crm.update` · `crm.delete` — objects: `people, companies, notes, opportunities, tasks` |
| **Apollo** | ⚠️ Needs key | `search_people` · `enrich_person` · `search_organizations` — **decision-maker / LinkedIn-style lookup** (our LinkedIn alternative; connect a key to use) |
| **Hunter** | ⚠️ Needs key | `domain_search` · `verify_email` (integration `inactive` — "Missing required fields: api_key") |

Also **connected but no toolbridge functions exposed:** Trello, Telegram (active integrations,
no functions surfaced in the audit).

---

## Part 2 — Snov.io direct API (reachable with our credentials)

Probed live (OAuth `client_credentials` → Bearer, `api.snov.io`):

| Endpoint | Result | Meaning |
|----------|--------|---------|
| `GET /v1/get-balance` | 200 — **765 credits**, teamwork on | Account active |
| `GET /v1/get-user-lists` | 200 — 1 prospect list | List management works |
| `GET /v1/get-user-campaigns` | 200 — `[]` | **Campaigns API exists** (none created yet) |
| `GET /v2/campaigns/{id}` | 200 ("campaign not found") | Campaign-detail endpoint exists |
| `POST /v1/send-email`, `/v1/campaigns/send`, `GET /v1/get-sender-mailboxes` | **404** | **No ad-hoc send endpoint** — Snov sends only via drip campaigns configured in its dashboard |

**Conclusion:** Snov the product *can* send (drip campaigns, dashboard-configured, HTML +
signature supported) — but there is no "send one email" API, and the workforce integration
exposes none of the campaign/list functions.

---

## Part 3 — Asks for the tech team

| # | Ask | Why | Where |
|---|-----|-----|-------|
| 1 | Make `zoho_mail.send` support **HTML** (`MIMEText(_subtype="html")` or `MIMEMultipart("alternative")`) | So the workforce can send branded email + rendered signatures | backend `zoho_smtp.py` |
| 2 | Expose Snov **campaign/prospect** functions in the toolbridge (`get-user-campaigns`, `add-prospect-to-list`, add-to-campaign) | So the workforce can feed enriched leads into a Snov drip campaign for real outreach | Snov integration plugin |
| 3 | Confirm/connect **Apollo** + **Hunter** keys | Apollo = decision-maker/LinkedIn-style lookup; both currently `Needs key` | integrations config |

---

## Part 4 — What works today (so outreach isn't fully blocked)

- **WhatsApp (Baian):** fully working, branded — approved templates render, and it supports
  **document/PDF** sends natively.
- **Email (branded):** via **Snov drip campaigns set up in the Snov dashboard** (Zoho mailbox
  as sender, HTML signature + template configured in Snov) — this renders correctly and adds
  sequencing/deliverability. Workforce enriches/verifies leads to feed it.
- **Email (plain-text/transactional):** `zoho_mail.send` from the workforce.
- **CRM + enrichment + verification:** Twenty CRM (full CRUD), Snov enrich/verify, Apollo/Hunter
  once keyed.

Signature asset for the tech team / Snov setup: `workforce/assets/email_signature.html`.

# 10 — Integration Keys (no secrets)

> **Reference for which integrations the workforce needs and where to get
> the keys.** This file does **NOT** contain actual secrets — those live
> in `.env` (which is gitignored).
>
> **Status (2026-07-07):** Twenty CRM is UP and integrated. Snov.io is
> connected and used for email enrichment + verification. Baian (WhatsApp)
> is **ACTIVE and verified working** (cloud-only — token lives only in the
> cloud integration config). See `07_open_items_and_status.md` for the
> current state of each integration.

---

## Required Integrations

| Integration | Purpose | Status | Where to get the key |
|-------------|---------|--------|---------------------|
| **OpenRouter** | LLM routing (all agents) | Required | https://openrouter.ai/keys |
| **Twenty CRM** | Lead storage + dedup | Active | `TWENTY_TOKEN` — JWT from your Twenty workspace |
| **Snov.io** | Email enrichment + verification | Active | https://snov.io — `client_id` / `client_secret` (or `user_id` / `user_secret` for v1) |
| **Zoho Mail** | Email outreach | Active | `ZOHO_MAIL` / `ZOHO_PASS` — from Zoho account |
| **Google Places API** | Lead generation | **RETIRED 2026-07-14** | Google Maps Platform in Saudi now requires a CNTXT corporate account — no access. Replaced by self-hosted `gosom/google-maps-scraper` (free) + Overpass/OSM (`scripts/fetch_leads_osm.py`). |
| **Baian** | WhatsApp outreach | **Active (cloud-only)** | Token lives only in the cloud integration config (`baian.navaia.sa`); redacted locally. Verified working 2026-07-07. |
| **Apollo.io** (optional) | Free decision-maker lookup | Optional | https://apollo.io — free plan with corporate email |
| **Hunter.io** (optional) | Free email pattern lookup | Optional | https://hunter.io — 25 searches + 50 verifies/mo free |

---

## How to Add Provider Keys

You have two ways. Pick one.

### Way 1 — API (or let an AI do it for you)

Base URL: `https://fareegi.navaia.sa/api/v1`
Auth header on every call: `x-api-key: YOUR_API_KEY` (create one in
Settings → API Keys).

```bash
curl -X POST https://fareegi.navaia.sa/api/v1/integrations \
  -H "x-api-key: YOUR_API_KEY" -H "Content-Type: application/json" \
  -d '{
        "workforce_id": "YOUR_WORKFORCE_ID",
        "plugin_name": "apollo",
        "config_json": { "api_key": "YOUR_APOLLO_KEY" }
      }'
```

Repeat with:
- `hunter` → `{"api_key": "…"}`
- `snov` → `{"client_id": "…", "client_secret": "…"}`
- `twenty` → `{"api_key": "…"}` (base URL is preset to `https://crm.navaia.sa`)

Check what's connected (secrets come back redacted):

```bash
curl "https://fareegi.navaia.sa/api/v1/integrations?workforce_id=YOUR_WORKFORCE_ID" \
  -H "x-api-key: YOUR_API_KEY"
```

### Way 2 — Let an AI do it

You can paste the Way 1 instructions into any AI model or Navaia Code and say:

> "Add my data-provider keys to my workforce using Way 1. My workforce ID is
> `<yours>`, my API key is `<yours>`, and here are my provider keys:
> Snov client_id/secret=…, Twenty=…" — it'll make the calls for you.

---

## Environment Variable Reference

> The actual values are in `.env` (gitignored). This table is just the
> shape — what each variable is for and which integration needs it.

| Var | Required for | Source |
|-----|--------------|--------|
| `OPENROUTER_API_KEY` | All agents (LLM) | OpenRouter dashboard |
| `SECRET_KEY` | JWT signing | `openssl rand -hex 32` |
| `ALLOWED_ORIGINS` | CORS | Comma-separated origins |
| `BUSINESS_NF` | Workforce API key | Navaia dashboard |
| `DEBUG` | Local dev | `true` for local |
| `NAVAIA_BACKEND_VERSION` | Backend version | Default `latest` |
| `API_PORT` | Host port | Default `8001` |
| `POSTGRES_USER` / `_PASSWORD` / `_DB` | Database | Defaults shown |
| `WEAVIATE_API_KEY` | Vector DB | Leave empty for anonymous |
| `GITHUB_TOKEN_ENC_KEY` | Token encryption | `Fernet.generate_key()` |
| `MY_PHONE` | User's phone (signature) | User's phone number |
| `TWENTY_TOKEN` | Twenty CRM | Twenty workspace |
| `TWENTY_SESSION` | Twenty CRM session | Twenty workspace |
| `ZOHO_MAIL` | Zoho account email | Zoho |
| `ZOHO_PASS` | Zoho account password | Zoho |
| `SNOV_USER_ID` | Snov.io enrichment | Snov.io |
| `SNOV_USER_SECRET` | Snov.io enrichment | Snov.io |
| `PLACES_API` | Lead generation | Google Cloud Console |
| `BAIAN_TOKEN` | WhatsApp outreach (Active — cloud-only) | Navaia team |

> **Container env var caveat:** only `OPENROUTER_API_KEY` is passed to the
> container by default. Other `.env` vars (`PLACES_API`, `TWENTY_TOKEN`,
> `SNOV_*`, `ZOHO_*`) are NOT available inside the container. They must be
> embedded in task descriptions or added to `docker-compose.yml`.

---

## Important

- The provider keys (Snov, Twenty, etc.) must be **your own** — sign up at
  each provider and use your keys.
- Don't share keys in group chats; paste them only into the form or your
  own API call.
- Until you connect a provider, your agents will ask you to connect it
  rather than fail — no key ever appears in the chat.
- This file is safe to commit. The actual `.env` file is gitignored.

---

## Resume Checklist (for each integration)

### Snov.io
1. Sign up at https://snov.io
2. Get `client_id` and `client_secret` (or `user_id` / `user_secret` for v1)
3. Add to `.env` as `SNOV_USER_ID` / `SNOV_USER_SECRET`
4. Test: `python scripts/check_snov_credits.py`

### Twenty CRM
1. Sign up at https://crm.navaia.sa
2. Get workspace JWT token
3. Add to `.env` as `TWENTY_TOKEN`
4. Test: `python scripts/configure_twenty.py`

### Zoho Mail
1. Sign up at https://www.zoho.com/mail/
2. Get account email + app password
3. Add to `.env` as `ZOHO_MAIL` / `ZOHO_PASS`
4. Test: send a single email via the integration

### Google Places API
1. Create project at https://console.cloud.google.com
2. Enable Places API (New)
3. Create API key
4. Add to `.env` as `PLACES_API`
5. Test: `python scripts/fetch_leads.py` (single vertical, limit 1)

### Baian (when token restored)
1. Get token from Navaia team
2. Add to `.env` as `BAIAN_TOKEN`
3. Test: send a single test message
4. Update `baian_capability_allowlist` in agent config
5. Run a small batch (5–10 leads) and review in dashboard
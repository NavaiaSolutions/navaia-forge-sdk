# Playbook — Lead Pipeline (fetch → clean → enrich → verify → import)

> SOP for the lead pipeline. Runs as **direct Python scripts** (not agent tool calls):
> the `moonshotai/kimi-k2.6` runtime produced malformed JSON for complex tool calls, so
> the agent **orchestrates** and the **scripts do the work**. Do not "fix" this by making
> the agent fetch — keep the scripts. Full script reference: `../09_canonical_scripts.md`.

## Preconditions
- `.env` has `TWENTY_TOKEN`, `SNOV_USER_ID`, `SNOV_USER_SECRET`. (**`PLACES_API` is retired** —
  Google Maps Platform in Saudi now requires a CNTXT corporate account we don't have.)
- For the primary fetch: Docker available (the scraper runs as a container).
- Local stack up + DB initialised (`scripts/setup_db.py`). See `deploy_and_sync.md`.
- **Single source of truth:** Twenty CRM. CSV files (`leads_enriched.csv`) from the initial Phase-1 run are historical reference only.

## Lead sources (post-Places, 2026-07-14)

| Source | Role | Cost | How |
|--------|------|------|-----|
| **`gosom/google-maps-scraper`** (open source, MIT) | **Primary** | Free | `docker run --rm -v <dir>:/work gosom/google-maps-scraper:latest-rod -input /work/queries.txt -results /work/leads_raw.csv -depth 3 -c 2 -geo "24.7136,46.6753" -lang ar -zoom 12 -exit-on-inactivity 3m`. **Use the `latest-rod` tag** — verified working 2026-07-14 (32 places incl. Arabic reviews from one query); the plain `latest`/v1.16.x tags are broken upstream (Playwright driver bug, issue #302; a locally patched build lives at `deploy/gmaps-scraper/Dockerfile` if rod ever regresses). Same search terms as the old Places flow, one per line. Returns name/address/phone/website/**reviews** (reviews feed the trust-locked pain enrichment from the SAME listing). Keep batches small (15–30) and concurrency low — no proxies needed at that volume; heavy scraping risks blocks and violates Google ToS. |
| **Overpass/OSM** (`scripts/fetch_leads_osm.py`) | Fallback/supplement | Free, keyless | Pure HTTP — runs anywhere incl. the cloud runtime. Riyadh coverage is thin (~30 phone-bearing SMBs across all verticals, probed 2026-07-14). Rotates public endpoints; one combined query per run. |

## Steps (run in order)
```bash
# 1. Fetch (pick per the table above; both write the same CSV schema, keep the source id)
docker run --rm -v "$PWD:/work" gosom/google-maps-scraper:latest-rod -input /work/queries.txt -results /work/leads_raw.json -json -extra-reviews -depth 3 -c 2 -geo "24.7136,46.6753" -lang ar -zoom 12 -exit-on-inactivity 3m
.venv/Scripts/python.exe scripts/fetch_leads_osm.py                # 1b. OSM fallback → leads_osm.csv

# CLOUD-BATCH PATH (preferred — the cloud does everything after the scrape):
.venv/Scripts/python.exe scripts/distill_scraped_leads.py leads_raw.json leads_scraped_compact.json  # scrape output → lead pool (NDJSON, JSON array or legacy CSV — sniffed)
.venv/Scripts/python.exe scripts/submit_lead_batch.py                                                # dispatch next batch to cloud Tariq
#   ^ repeat per batch: it skips already-submitted leads (submitted_task marker in the pool file)
#     and each task hard-stops at the channel-agnostic HITL gate before sending.
#     Steps 2-7 below are the LOCAL scripted path; a cloud batch task replaces them.
.venv/Scripts/python.exe scripts/step1_clean.py                   # 2. address/phone/domain clean
.venv/Scripts/python.exe scripts/enrich_emails.py                 # 3a. website crawl + web search → updates CRM
.venv/Scripts/python.exe scripts/fetch_emails_snov.py             # 3b. Snov.io v2 email fetch (async) → updates CRM
.venv/Scripts/python.exe scripts/verify_all_emails.py             # 4. Snov.io v2 verify (.sa → "likely valid") → updates CRM
.venv/Scripts/python.exe scripts/import_selected_leads.py --from-pool leads_enriched_people.json   # 5. import to Twenty CRM (person-first, DEDUPED against existing Mjeed phones, idempotent).
.venv/Scripts/python.exe scripts/verify_import.py                 # 6. confirm the ACTUAL added count
.venv/Scripts/python.exe scripts/enrich_reviews.py                  # 7. TRUST-LOCKED review pain (place_id + phone verified) → CRM → feeds {trigger_line}
```
> **No dedup step:** the **Twenty CRM backend handles duplicates**, so the agent does NOT check for dups — that step is removed (it cost tokens for nothing). Add all leads; the CRM dumps duplicates; **count only what was ACTUALLY added.** When asked for **N** leads, if the added count is below N (CRM dumped some), **fetch + add more until N NEW records exist** — the number you report equals the number actually in the CRM. `graphql_dedup.py` / `crosslang_dedup.py` are kept only as **manual one-off** reconciliation tools, NOT part of the flow.
>
> **Review enrichment (step 7) is TRUST-LOCKED:** it reads a lead's Google reviews **only** via the exact `place_id` (never a name search) and **only** when the Places phone matches the lead's phone — so it can never pull a similarly-named different company. It then reasons the lead's specific pain from *those* reviews and appends it to the **exact** CRM lead.

## Hard rules
- **Real data only** — record only what a real source (Google Places / Overpass / Snov)
  returns. Never invent a field; leave unknowns empty.
- Every lead needs at least a phone or email. Riyadh region only.
- Twenty CRM link-object fields (`domainName`, `linkedinLink`, `annualRevenue`) are
  `{"primaryLinkUrl": …}`, not strings. `createdBy` is required. Use the 5 exact sector
  names. See `../agents/tariq_sdr_lead_fetcher.md` for schema + CRM quirks.

## Orchestration
Ahmed (GM) delegates "find leads" to **Tariq**. Tariq runs this pipeline, reports counts
back. Scoring/prioritisation model: `../05_lead_scoring_model.md`.

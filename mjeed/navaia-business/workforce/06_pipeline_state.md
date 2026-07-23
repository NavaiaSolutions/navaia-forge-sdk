# 06 — Pipeline State (Post-Import, as of 2026-07-06)

> **Authoritative reference for the current state of the data and CRM.**
> Read this before re-running dedup/enrichment/import scripts.

---

## HARD RULE: Only touch Mjeed's leads

**The CRM is shared** — other people add leads too. **Every CRM query MUST filter by `createdBy.name` containing "Mjeed".** Never read, message, or act on leads added by other people. This applies to all scripts, ad-hoc queries, and agent tasks.

- Filter people: check `createdBy.name` includes "Mjeed"
- Filter companies: check `createdBy.name` includes "Mjeed"
- If a script dumps all CRM data without this filter, it is **broken** — fix it before running.

## CRM — Twenty CRM is live (shared system)

- **Base URL:** `https://crm.navaia.sa`
- **Auth:** `TWENTY_TOKEN` in `.env` (header: `Authorization: Bearer <token>`)
- **REST endpoint:** `/rest/companies` (POST), `/rest/people` (POST with `companyId`)
- **GraphQL endpoint:** `/graphql` (use for pagination — see below)
- **CRM is shared** — other people add leads too. Only message leads where `createdBy.name = "Mjeed"`. Do not message leads added by other people.
- **Current state:** 645 companies, ~491 contacts. Of these, **36 are from Mjeed's Riyadh lead run** (35 bulk + 1 test = شركة اتقان العقارية). The rest were added by other people.

---

## Critical CRM Quirks (don't re-discover these)

| Quirk | Detail |
|-------|--------|
| **REST pagination is broken** | `?after=<cursor>` is silently ignored. Always returns page 1. **Do not use REST for reads across pages.** |
| **GraphQL pagination works** | Use `first` + `after` + `cursor` on the `/graphql` endpoint. `scripts/graphql_dedup.py` is the working pattern. |
| **Link-object fields** | `domainName`, `linkedinLink`, `annualRevenue` are link objects: `{"primaryLinkUrl": "https://..."}`. Not strings. |
| **`createdBy` is required** | Format: `{"source": "AGENT", "name": "Mjeed using "}`. The trailing space is intentional (matches the test script's pattern). |
| **`address` is structured** | Use `{"addressStreet1": "..."}`. Not a flat string. |
| **Sector field** | Free-text on Company and Person. Use the 5 vertical names from §5.1 exactly. |
| **Person needs `companyId`** | UUID returned from `createCompany`. Confirmed working as `companyId` in the request body. |

---

## Pipeline Steps (in order — do not skip)

1. **Raw fetch** → Twenty CRM (Google Places API, direct import)
2. **Email enrichment (website crawl + web search)** → Twenty CRM via `scripts/enrich_emails.py` + `scripts/fetch_emails_snov.py`
3. **Email verification (Snov.io v2)** → Twenty CRM via `scripts/verify_all_emails.py`
4. **Post-import verify** → `scripts/verify_import.py` — GraphQL `totalCount` check vs expected count

> **No dedup step.** The Twenty CRM backend handles duplicate elimination automatically. Never run an agent-side dedup step — it costs tokens for nothing. The old dedup scripts (`graphql_dedup.py`, `crosslang_dedup.py`) are kept as manual one-off reconciliation tools only — not part of the pipeline.

---

## Snov.io v2 — the Only Working Endpoints

| Purpose | Endpoint | Method | Notes |
|---------|----------|--------|-------|
| Start email verify | `/v2/email-verification/start` | POST | Body: `{"email": "..."}`. Returns `task_hash`. |
| Get email verify result | `/v2/email-verification/result?task_hash=<hash>` | GET | Returns `smtp_status`. |
| Start domain email search | `/v2/domain-search/domain-emails/start` | POST | Body: `{"domain": "..."}`. Returns `task_hash`. |
| Get domain email result | `/v2/domain-search/domain-emails/result/<task_hash>` | GET | Returns list of emails. |

**All other endpoint variants (`/v1/email-verifier`, `/v2/email-verifier`, etc.)
return 404. Do not retry them — they don't exist.**

**`.sa` domain caveat:** SMTP probes for Saudi domains return
`smtp_status: unknown` — the mail servers don't respond. Treat as "likely valid,
unverified at SMTP layer." Don't reject these leads for that reason.

**Snov.io credits:** 805 balance, resets in ~18 days from 2026-07-06.

---

## Cross-Language Dedup Approach (archived reference)

> The cross-language dedup script (`scripts/crosslang_dedup.py`) is kept as a manual
> one-off reconciliation tool only. It is **not** part of the pipeline — the CRM
> backend handles dedup. This section is historical reference for the approach used
> during the initial import (2026-07-06).

The approach catches Arabic/English duplicate company names by:
1. Fetching all companies + contacts via GraphQL.
2. Normalizing: lowercase, strip diacritics, remove `شركة` / `مؤسسة` / `Co.` /
   `LLC` / `Ltd` / `Inc`.
3. **Transliteration match:** map Arabic chars to Latin equivalents (ا→a,
   ع→a/aa, ح→h, etc.) and compare.
4. **Domain match:** exact or suffix match (e.g. `saudico.com.sa` matches
   `www.saudico.com.sa`).
5. **Phone match:** normalize to digits only, last 9 digits must match.
6. **Address overlap:** token Jaccard similarity ≥ 0.6 on street/city tokens.

**Result on 2026-07-06:** 0 duplicates found across 645 companies.

---

## Current Data State (single source of truth: Twenty CRM)

> The Twenty CRM is the single source of truth for all leads. The CSV files were
> a Phase-1 workaround before CRM access was available. They are no longer needed
> as an intermediate data store.

| Source | Count | Status |
|--------|-------|--------|
| **CRM (Twenty)** | 645 companies, ~491 contacts | **THE source of truth** — includes 35 from the initial Riyadh run + 1 test (اتقان) |
| **`leads_enriched.csv`** | 36 | **Historical only** — do not use as an active data source. Keep as reference for the initial import. |

**Before re-running import:** run `scripts/verify_import.py` to confirm current CRM state. The 35 already-imported companies are in CRM and will be auto-deduped by the CRM backend if re-imported. Add all leads; the CRM dumps duplicates; count only what was actually added.

---

## Lead CSV Schema (canonical)

```
company_name: Business name from Google Places
domain_name: Cleaned domain (e.g., saudico.com.sa)
address: Full formatted address from Google Places
phone: International phone number (+966...)
email: Email from Snov.io (if found, otherwise empty)
email_status: found_unverified | no_emails_in_snov | no_domain | email_domain_mismatch
sector: Contracting & Facilities | Finance & Debt Collection | Private Clinics | Real Estate | Training Institutes
vertical_tier: Tier 1 | Tier 2
created_by: Mjeed using [Tariq SDR Agent]
lead_source: Google-Places
place_id: Google Places ID (for dedup tracking)
```

---

## Eliminated Junk (deleted 2026-07-06 — do not recreate)

These were stale/intermediate/duplicate and have been **deleted** per the
"useful data upfront, no junk" rule. Listed so nobody re-generates them by
habit:

| File | Why it was junk |
|------|-----------------|
| `leads.csv`, `leads_final.csv`, `leads_verified.csv` | 50-row raw/intermediate first/second-run stages, superseded. |
| `leads_to_import.csv` | 48-row pre-dedup intermediate. |
| `leads_clean.csv` | 36-row subset of `leads_enriched.csv`. |
| `leads_verified_final.csv` | Byte-identical duplicate of `leads_clean.csv`. |
| `scripts/existing_crm_data.json` | Stale cache (claimed 21,500; actual 645). |
| `scripts/dedup_output.txt`, `scripts/test_crm.json` | Throwaway console dump / test artifact. |

---

## Per-Vertical Lead Counts (from Tariq's initial run)

| Vertical | Tier | Leads |
|----------|------|-------|
| Contracting & Facilities | T1 | (in CRM) |
| Finance & Debt Collection | T1 | (in CRM) |
| Private Clinics (dental) | T1 | (in CRM) |
| Real Estate | T2 | (in CRM) |
| Training Institutes | T2 | (in CRM) |
| **Total (Tariq's leads)** | | **36** |

> These counts are from Tariq's initial import (2026-07-06). Current CRM totals are higher because other people add leads too. Query CRM by `leadSource: "Google-Places"` or `createdBy` to get Tariq's subset.

---

## Lead-source configuration (Google Places API RETIRED 2026-07-14)

> The Google Places API is no longer usable: Google Maps Platform in Saudi now requires a
> CNTXT corporate account, which we don't have. The `PLACES_API` key is dead — never ask for
> it or embed it. Historical Places references in this file describe the initial 2026-07-06 run.

- **Primary:** self-hosted open-source Google Maps scraper (`gosom/google-maps-scraper`, MIT,
  free) via Docker — same search terms, returns name/address/phone/website/reviews.
  See `playbooks/lead_pipeline.md` for the exact command and limits.
- **Fallback:** Overpass/OSM via `scripts/fetch_leads_osm.py` — free, keyless, runs anywhere;
  Riyadh coverage is thin (~30 phone-bearing SMBs total, probed 2026-07-14).

### Filtering rules (any source)
- Address/geography must be Riyadh ("Riyadh" / "الرياض" or inside the Riyadh bbox)
- Must have a phone number (no phone = skip)
- Deduplicated by source id (Maps place id / OSM id) and company name
- No fabricated data — only real scraped/API results

---

## Verification Process (how 50 leads became 36)

1. **Phone validation:** Regex for Saudi +966 format — all 50 passed
2. **Address validation:** Must contain "Riyadh" — all 50 passed
3. **Domain extraction:** Parsed from website URL, cleaned (removed protocol,
   www, path)
   - 40 leads have valid domains
   - 10 leads have no website (domain missing)
4. **Snov.io email count check** (v1 `get-domain-emails-count`, free API):
   - 27 domains have emails in Snov database
   - 13 domains have 0 emails
   - 10 leads have no domain
5. **Snov.io email discovery** (v2 `domain-search/domain-emails` +
   `generic-contacts`):
   - 25 leads with real email addresses found
   - 1 lead email cleared (BROS Dental — Instagram URL was treated as domain,
     produced `info@instagram.com`)
   - Email selection priority: info@ > contact@ > sales@ > admin@ > first
     available
6. **CRM dedup** (English name + domain): 12 dups removed → 36 leads
7. **Cross-language dedup:** 0 dups found
8. **Bulk import:** 35 created (1 excluded during final preflight)
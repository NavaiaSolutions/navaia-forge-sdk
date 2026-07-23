# Task spec — Lead finding (Maps scrape / OSM → Twenty CRM)

> Self-contained task spec. In practice the pipeline runs as **direct scripts**
> (`../playbooks/lead_pipeline.md`) for reliability; this spec is for when the work is
> dispatched to the agent instead. Dispatch helper: `scripts/create_lead_task.py`
> (assigns to Tariq). **Google Places API is retired** (CNTXT-corporate-only in Saudi) —
> do not inject a `PLACES_API` key.

**Assign to:** Tariq (SDR).

**Title:** `Find {{N}} real targeted leads in Riyadh across 5 verticals → Twenty CRM`

**Description (key points the dispatched description must contain):**
```
Find {{N}} REAL business leads in Riyadh across the 5 verticals and add to Twenty CRM.
LEADS FINDING ONLY — do NOT send any emails or messages.

Verticals + exact sector values:
- Contracting, Maintenance & Facilities  -> "Contracting & Facilities"
- Finance, Installment & Debt Collection -> "Finance & Debt Collection"
- Private Specialty Clinics (dental/derm/cosmetic/physio; NOT hospitals) -> "Private Clinics"
- Real Estate & Property Management       -> "Real Estate"
- Training Institutes                     -> "Training Institutes"

Source: a pre-scraped Google Maps CSV provided with the task (from the self-hosted
gosom/google-maps-scraper — see ../playbooks/lead_pipeline.md), and/or Overpass/OSM
(free keyless HTTP; thin Riyadh coverage — report honestly if the count can't be met).
The Google Places API is RETIRED — never request a PLACES_API key.

Twenty CRM: use the native Twenty CRM integration tool (crm.navaia.sa).
Create Company (POST /rest/companies) then Person (POST /rest/people with companyId).
Link-object fields = {"primaryLinkUrl": ...}. createdBy = {"source":"AGENT","name":"Mjeed","context":{}}.

Rules: REAL DATA ONLY (never invent; leave unknown fields empty). No duplicates (search CRM
by name first). Every lead needs a phone. Riyadh only. Report total added, broken down by vertical.
```

Full field schema, CRM quirks, and Snov enrichment: `../agents/tariq_sdr_lead_fetcher.md`.

# 05 — Lead Scoring Model

> **Rules-based 0–100 scoring model** for prioritizing outreach. Start
> transparent and rules-based; move to predictive once we have volume.
>
> **Implementation is the scripting model's work.** This file is the spec
> the scripting model will use to build the scoring pipeline.

---

## Philosophy

Weight **trigger events** heavily — external buying-intent correlates with
closed-won far more than engagement signals.

**Tune after first send batch.** The weights below are first-pass; real data
should be folded in after 50–100 sends to recalibrate.

---

## Scoring Signals & Weights

| Signal | Weight | Source | How to detect |
|--------|--------|--------|---------------|
| **Vertical fit** (appointment/inquiry-heavy: clinics, dentists, salons, reservation restaurants) | +30 | Lead's sector field | Sector ∈ {"Private Clinics"} or "has manual booking channel" |
| **Manual booking/inquiry channel** (phone/DM/form, active IG/WhatsApp business) | +20 | Lead's website / IG / Google listing | No online booking widget; phone/WhatsApp listed; IG active |
| **Has verified email** | +20 | Snov.io verification result | `email_status == "verified"` or `"found_unverified"` with `.sa` domain (treated as likely valid per Snov caveat) |
| **Trigger event / review pain** (reviews citing "no reply", missed calls, slow booking) | +15 | **`scripts/enrich_reviews.py`** — trust-locked to the lead's own Google reviews (exact place_id + phone match) → `leads_reviews.csv` + CRM | Non-empty `pain_line` for the lead. Also surfaced as `{trigger_line}` in the outreach opener. |
| **Employee count 50+** (operator rule 2026-07-20 — larger contract value, real ops load) | +10 | `scripts/enrich_company_size.py` (company's own website) | Self-published headcount claim ≥ 50. See "Sizing a company" below — this is NOT inferable and must never be guessed. |
| **Has website / LinkedIn** (digital maturity) | +10 | Lead's website URL, LinkedIn | Non-empty `domainName` or `linkedinLink` |
| **Named decision-maker identified** | +10 | Enrichment output | Person record exists with `decisionMaker: true` |

**Cap at 100.**

---

## Score Buckets

| Score | Bucket | Action |
|-------|--------|--------|
| 80–100 | **Hot** | Send first batch, high priority, manual sends acceptable |
| 50–79 | **Warm** | Send in normal cadence, automated |
| 20–49 | **Cool** | Send in later batch, test messaging first |
| 0–19 | **Cold** | Defer or skip (re-evaluate in next quarter) |

---

## Vertical Fit Detail

The 5 verticals from §5.1 are **all** in-scope, but the "vertical fit" score
applies when the lead is in a high-pain, high-margin vertical with a manual
booking/inquiry channel that our product can directly address:

| Vertical | Vertical fit score? | Notes |
|----------|---------------------|-------|
| Private Specialty Clinics (dental/derm/cosmetic/physio) | **+30** | Direct fit — missed appointments, no-shows |
| Contracting/Facilities | 0 (use other signals) | Fit is via RFQ/follow-up, not appointment-channel |
| Finance/Debt Collection | 0 (use other signals) | Fit is via collection consistency, not booking-channel |
| Real Estate | 0 (use other signals) | Fit is via response time, not booking-channel |
| Training Institutes | 0 (use other signals) | Fit is via registration surge, not booking-channel |

> **Note:** the +30 vertical fit is a "bonus" on top of the other signals. It's
> designed to push clinics to the top of the send list because they're the
> tightest vertical fit for the product. Other verticals can still score high
> via the other signals (e.g., Finance + verified email + trigger event +
> named decision-maker = 55+).

---

## Sizing a company (the 50+ rule)

> **Changed 2026-07-20 by operator decision.** The old rule was "3–50 employees, fast
> owner decision". It is now **50+**: larger contract value and a real operational load
> to automate. The old band is dead — do not reintroduce it.

**There is no headcount field in the pipeline.** Twenty's `employees` is empty on every
one of Mjeed's companies and no LinkedIn URLs are stored. Sizing is therefore a
deliberate, per-lead step — not something the ranker knows for free.

Sources, in the order they should be tried (researched 2026-07-20):

| Source | Use it? | Why |
|--------|---------|-----|
| **Company's own website** | ✅ **Primary** | Self-published, public, no ToS conflict. `scripts/enrich_company_size.py` reads homepage + about/من-نحن for an explicit claim ("over 50 certified professionals"). Free. |
| **Snov.io company-by-domain** | ⚠️ **Paid fallback** | Licensed B2B data, ~1 credit/domain. Only for leads the crawl could not size, and only on explicit operator approval — the crawl script prints the candidate list and cost, and spends nothing itself. |
| **LinkedIn** | ❌ **Never** | Scraping violates the User Agreement regardless of tooling; 2026 enforcement is fingerprint/IP-based; LinkedIn sued Proxycurl out of business in 2025 for this exact activity. A footer LinkedIn URL may be *recorded* for a human to open — never fetched by a script. |
| **Wathq / GOSI / Qiwa** | ❌ **Not for prospecting** | Wathq API 18 does serve GOSI employment data, but it is consent-gated to the establishment itself and is personal data under PDPL (penalties to SAR 5M). Lawful for checking our OWN headcount; not a prospect's. |

**GOSI's official bands** are the reference definition: 1–5 small, 6–49 micro,
**50–249 medium**, 250+ large. So "50+" means "medium or larger" in Saudi regulatory terms.

### Size proxy vs. size fact

`scripts/rank_priority_leads.py` ranks all Not Contacted leads for free using a **size
proxy** — branch count (same business across multiple pool listings), Saudi legal form
(`مجموعة`/`قابضة` > `شركة` > `مكتب`/`مؤسسة`), owning a real domain vs. an aqar.fm page,
and review volume. The proxy is a **hypothesis that orders the crawl queue**. It is never
a headcount and must never be written to `leadScore` as if it were one. A lead the crawl
cannot size is `unknown` — not "small", not "large".

---

## Trigger Event Detection (cheapest signals first)

| Signal | Detection method | Confidence |
|--------|------------------|------------|
| Google review mentions "no reply" / "ما ردّوا" | Text search on reviews | Medium |
| Recent hiring post for front-desk / CS | LinkedIn / Google Jobs | High |
| New website or recent redesign | Archive.org `Wayback Machine` | High |
| New online booking system launched | Site crawl | High |
| New branch opened | Google Places new listing | High |
| Recent negative review spike (>2 in 30 days) | Google reviews | Medium |

**Cap trigger events at +15 total** (even if multiple signals are present —
avoid double-counting the same underlying event).

---

## What This Model Does NOT Consider (intentionally)

- **Engagement with our previous emails** — we don't have enough historical
  data to weight this meaningfully yet
- **Social media follower count** — weak signal for SMBs in our verticals
- **Revenue** — rarely accurate for SMBs; skip unless verified from a
  primary source
- **Industry awards / press** — irrelevant for the target verticals

---

## Implementation Notes (for the scripting model)

1. **Read from Twenty CRM.** Query only Mjeed's leads (`createdBy.name = "Mjeed"`) — other people add leads to the CRM too.
2. **Compute the score** for each lead using the signals above.
3. **Bucket and sort** by score descending.
4. **Cap at 100.**
5. **Output** to memory or a temp file; the outreach pipeline reads from CRM directly.
6. **Hand off to Tariq** — he reads the scored leads from CRM and sends in bucket order (Hot → Warm → Cool).

### Pseudocode

```python
def score_lead(lead):
    score = 0
    signals = []

    # Vertical fit
    if lead.sector == "Private Clinics" and has_manual_booking_channel(lead):
        score += 30
        signals.append("vertical_fit_clinics")

    # Manual booking/inquiry channel
    if has_manual_booking_channel(lead):
        score += 20
        signals.append("manual_booking_channel")

    # Has verified email
    if lead.email and lead.email_status in ("verified", "found_unverified"):
        score += 20
        signals.append("verified_email")

    # Trigger event
    if has_trigger_event(lead):
        score += 15
        signals.append("trigger_event")

    # Employee count
    if 3 <= lead.employee_count <= 50:
        score += 10
        signals.append("employee_count_3_50")

    # Has website or LinkedIn
    if lead.domain or lead.linkedin:
        score += 10
        signals.append("digital_maturity")

    # Named decision-maker
    if has_named_decision_maker(lead):
        score += 10
        signals.append("named_decision_maker")

    return min(score, 100), signals
```

---

## Calibration Plan (after first send batch)

After 50–100 sends, measure reply rate by signal and re-weight:
- If "verified email" predicts reply strongly → keep at +20
- If "vertical fit" is noisy (clinics don't reply more than other verticals)
  → drop to +15 and redistribute
- If "trigger event" is the strongest predictor → consider raising to +25

**Target:** 10–15% reply rate (best-in-class on tight segments).

---

## Open Questions for the User

- Should we add a "company size penalty" for leads with employee_count > 200?
  (Longer sales cycle, more decision-makers.)
- Should we weight "Riyadh-based" higher than other Saudi cities?
- Should we add a "language preference" signal (Arabic-only vs bilingual)?
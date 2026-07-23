# Playbook — Email outreach (Snov.io campaign → Zoho mailbox)

> SOP for outbound email. **Lina writes the copy; Tariq sends it.** The send path is
> **Snov.io campaign → connected Zoho mailbox** (`ops@navaia.sa`) — **never call Zoho Mail
> send directly.**

## Preconditions
- Snov.io connected (`SNOV_USER_ID`/`SNOV_USER_SECRET`), Zoho mailbox connected on the
  workforce (verify via `scripts/check_cloud_integrations.py`).
- Copy is ready: Lina has produced finished, approved per-lead templates from
  `../04_outreach_templates.md` (5 verticals × 3 touches). See `../agents/lina_marketing.md`.
- Leads live in Twenty CRM / `leads_enriched.csv`, scored per `../05_lead_scoring_model.md`.

## Steps
1. **Lina → copy.** For each lead's vertical, fill per-lead tokens (`{honorific+name}`,
   company noun, `{pain_line}`, `{benefit_pair}` — pick 2 of 3: cost −40% / profit +30% /
   productivity). **No signature in the body** — Snov.io auto-appends the account's configured
   signature (verified 2026-07-13). Do not embed one or pass `--signature-file`, or it
   double-stamps. Reference copy: `../assets/email_signature.html`; the signature's `M` phone is
   Baian's WhatsApp number `+966 58 284 1599` (the lead contact), distinct from the rep's phone.
2. **Tariq → send.** Create/launch a **Snov.io campaign** using the Zoho mailbox as the
   connected sender. Prioritise by lead score.
3. **Cadence:** day 0 / +3 / +7. Send **Sun–Thu ~10am–12pm AST**, never Fri–Sat.
4. **Deliverability:** warmed domain; **plain-text** cal.com link (not hyperlinked); no
   tracking pixels; start **20/day**, ramp to **50/day** after a week; personalised subjects.
5. **Replies:** positive → cal.com link; booked → confirm; negative → graceful close;
   no reply after +7 → end cadence. Log sends + replies to the Fareegi dashboard.

## Attachments — the executive summary PDF, one per vertical

Each vertical gets the executive summary for the agent team it is being sold. The mapping is
`outreach.ATTACHMENT` (single source of truth); files live in `assets/attachments/`
(gitignored — Snov keeps its own copy once uploaded, so the payload never carries the binaries).
`python scripts/outreach.py --email-only` prints the right file for whichever verticals are in
the batch.

| Vertical | File | Size |
|---|---|---|
| Real Estate | `نڤايا — ملخّص تنفيذي · فريق المبيعات العقاري الذكي.pdf` | 710 KB |
| Contracting & Facilities | `نڤايا — ملخّص تنفيذي · فريق المناقصات والمبيعات الذكي.pdf` | 761 KB |
| Training Institutes | `نڤايا — ملخّص تنفيذي · فريق المناقصات ونجاح العملاء.pdf` | 770 KB |

**This is a MANUAL dashboard step, and it cannot be automated today.** Snov has no ad-hoc send
endpoint (`/v1/send-email`, `/v1/campaigns/send` both 404, probed live) and **no attachment or
file-upload endpoint anywhere in its API**, so no tool wrapping that API can ever attach. Snov
sends only via drip campaigns, which is also the only place a file can be attached. So: **one
campaign per vertical**, and attach that vertical's PDF to the campaign's email element. Snov's
limit is 6 MB total per campaign; every file above is far under it. Full probe results:
`../SNOV_API_CAPABILITIES_2026-07-21.md`.

> **Correction (2026-07-21).** This section previously said the workforce's Snov integration
> "exposes enrich/verify only — no campaign or send functions". That was wrong. It exposes
> `snov.domain_search`, `snov.find_email`, `snov.verify_email` and **`snov.send`**, and a live
> test send succeeded. But `snov.send` takes only `to`/`subject`/`body`/`first_name`/`last_name`
> — **no attachment parameter, and it creates a brand-new single-recipient campaign on every
> send**, so it can never deliver into a dashboard campaign that has a PDF attached. Enrolment
> into the three vertical campaigns must go through `scripts/snov_push.py`
> (`POST /v1/add-prospect-to-list`), not through Tariq's tool. See the `snov.send` schema entry
> in `OPEN_ITEMS.md`.

**Do not attach on touch 1.** Snov's own guidance is that an attachment on a first cold email
raises spam classification sharply, and this playbook already optimises hard for deliverability
(plain-text cal.com link, no tracking pixels, 20/day ramp). Attach from **touch 2 (+3 days)**
onward, once the recipient has engaged — or link the PDF in touch 1 instead of attaching it.
Sending a 750 KB attachment to a cold Saudi SMB inbox on first contact risks the whole domain's
reputation, which is worth far more than the attachment.

## Note
Email sending automation is not yet wired as a script (unlike the lead pipeline and the
Baian send). When wired, add a canonical `scripts/` entry and link it here.

# 02 — End-to-End Flow (Happy Path)

> The complete orchestration flow from user task to sent outreach, with all
> handoffs between agents documented.

---

## Happy Path (8 steps)

### 1. User assigns a task to the workforce

Via SDK or Fareegi dashboard. Example:
> "Find 20 SaaS founders in Riyadh and reach out."

The task is assigned to the workforce as a whole. Ahmed (GM) receives it.

### 2. Ahmed (GM) parses the task

Ahmed enters **Conversational Chat Mode** if the task is ambiguous. He asks
clarifying questions, summarizes his understanding, and only once confident
proceeds.

For clear tasks, he proceeds directly to delegation.

### 3. Ahmed routes the first hop to Rashid (Scraper)

Ahmed ends his output with `[route:rashid]` and nothing else. He never performs the scrape
himself — not even when the task says "JDI" or "just testing".

Rashid runs the lead-fetch stage (see `agents/rashid_scraper.md`):
1. Raw fetch via the self-hosted Google Maps scraper (primary) or Overpass/OSM
   (fallback) — the Google Places API is retired (CNTXT-only in Saudi)
2. Contact extraction from publicly visible site content (no Snov.io at this stage)
3. Qualification against `<target_scope>` — drops out-of-vertical and micro operations
4. Compiles ONE structured batch and ends with `[route:nora]`

**Rashid writes nothing to the CRM.** If scraping returns nothing or a credential is missing,
he reports the exact error and ends `[WAITING:BLOCKED]` — he never invents leads to fill a gap.

### 3b. Nora scores and performs the CRM import

Nora is the **only** agent that writes leads to Twenty CRM (see `agents/nora_scorer.md`):
1. Eligibility-check the batch; report dropped counts and reasons
2. Score each survivor 0–100 per the §11.5 rubric
3. Import linked Company + Person under `createdBy.name = "Mjeed"`, setting `sector`,
   `leadScore`, and `leadStatus = "Not Contacted"`; overflow detail goes to Notes
4. Ends with `[route:lina]`

No dedup steps — the Twenty CRM backend handles duplicate elimination automatically. Nora
reports actual-added count. Only Mjeed's leads are ever read or written.

### 4. Ahmed delegates outreach — Lina writes, Tariq sends

Outreach is not an agent; it's a two-step handoff Ahmed orchestrates:

**Lina (Marketing) — writes:**
- Receives the scored, CRM-imported batch from Nora via `[route:lina]` — per-lead context
  (sector, pain, decision maker) + framing ("first-touch cold reach") + vertical.
- The routed payload is truncated at 12,000 chars; if only CRM ids arrive, Lina reads the
  leads back from the CRM rather than guessing.
- Produces finished, approved copy from `04_outreach_templates.md`: subject + body per
  touch, benefit pair chosen, tokens filled (`{honorific+name}`, `{pain_line}`,
  `{benefit_pair}`, vertical noun). WhatsApp variant is shorter.

**Operator approval (HITL gate, channel-agnostic) — between Lina and any send:**
- The rendered messages (subject + body, tokens filled) are raised to the operator as a
  HITL question on the task. He approves/skips from **any** channel — Fareegi dashboard,
  Telegram (which relays the same gate), or elsewhere. The approval is about seeing the
  copy; the channel never matters. Nothing is sent unapproved.

**Tariq (SDR) — sends (only after approval):**
- Pulls lead + context from Twenty CRM.
- Applies the §11.5 lead score to prioritize.
- **Email:** launches a **Snov.io campaign** using the connected **Zoho mailbox**
  (`ops@navaia.sa`) — never Zoho-direct.
- **WhatsApp:** sends via **Baian** — **cloud-only**, so Ahmed routes the task to the
  cloud runtime; Tariq never sends Baian locally.
- Logs every send + reply to the Fareegi dashboard.
- Updates CRM `leadStatus` on send: first email → `"Emailed"`, first WhatsApp → `"WhatsApped"`.

### 6. Ahmed aggregates outcomes

Ahmed collects:
- Number of leads found
- Number of emails sent
- Open / reply / conversion rates (when available)
- Any errors or escalations

He updates the task status and surfaces results to the user via the dashboard.

### 7. Replies / inbound signals flow back (CRM is the record)

Every inbound signal updates the CRM **first**, then notifies Ahmed:

1. **Email reply** → Zoho Mail → webhook / poll
   → Ahmed updates CRM: `leadStatus = "Replied"` on the Person, logs reply content
   → Also logged to Fareegi dashboard
2. **WhatsApp reply** → Baian → webhook / dashboard
   → Ahmed updates CRM: `leadStatus = "Replied"` on the Person, logs reply content
   → Also logged to Fareegi dashboard
3. **cal.com booking** → cal.com webhook
   → Ahmed updates CRM: `leadStatus = "Meeting Booked"` on the Person
   → Also logged to Fareegi dashboard

Ahmed then routes follow-ups based on reply tone:
- Positive reply → confirm cal.com booking + WhatsApp option
- Question reply → answer or route to specialist
- Negative reply → graceful close, set `leadStatus = "Closed"`
- No reply after +7 → end of cadence, set `leadStatus = "Unresponsive"`

> **Further updates are manual only.** No automated status transitions beyond the lifecycle documented in `agents/tariq_sdr_lead_fetcher.md#lead-status-lifecycle`.

### 8. Follow-up cadence (day 0 / +3 / +7)

- **Day 0:** Touch 1 (pain → actions → impact → compliance → link)
- **Day +3:** Touch 2 (new angle: proof point or specific number)
- **Day +7:** Touch 3 (warm door-open breakup)
- **On positive reply:** Confirm cal.com + WhatsApp option; switch to hard CTA

---

## Agent Handoff Map

The chain is a single sequential run of `[route:...]` markers. Each arrow below is a REAL
cloud edge; the marker in brackets is what the agent must emit as its final line (lowercase).

```
User
  ↓ (assign task)
Ahmed (GM — routes the first hop only)
  ↓ [route:rashid]
Rashid (Scraper — scrapes Maps/OSM; writes NOTHING to CRM)
  ↓ [route:nora]
Nora (Scorer & Importer — eligibility, score 0-100, THE CRM import under Mjeed)
  ↓ [route:lina]
Lina (Marketing — Touch-1 Arabic copy, tokens filled)
  ↓ [route:tariq]
Tariq (SDR/Sender)
  ↓ presents rendered manifest, STOPS at [WAITING:QUESTION]
[Operator HITL approval — any channel: dashboard / Telegram / …]
  ↓ (approved)
Tariq (sends: email via Snov→Zoho; WhatsApp via Baian on cloud; updates CRM leadStatus)
  ↓ [route:ahmed]
Ahmed (GM — aggregates every step, reports to operator, ends [DONE])
```

**Not in this chain:** Ghida (Creative — visual identity, RTL/Arabic layout) and Fahad
(Account Manager — post-sale, expansion).

> **Routing is literal and case-sensitive.** Edges match `contains:[route:name]` in lowercase.
> `[ROUTE:NAME]` matches nothing, fails silently, and strands the chain — this caused the
> 2026-07-19 incident where Ahmed looped, then fabricated CRM leads rather than stopping.
> An edge also fires only ONCE per chain: never route backwards or re-emit a marker.

---

## Failure Modes & Escalation

| Failure | What happens | Escalation |
|---------|--------------|------------|
| Tariq can't find enough leads | Reports back to Ahmed with count | Ahmed asks user to broaden criteria |
| Email send fails | Logged to dashboard, retry queue | If >10% fail rate, Ahmed escalates |
| Lead has no email | Skipped (Tariq should have flagged) | Ahmed asks user to provide channel |
| Recipient replies negatively | Routed to Ahmed | Ahmed sends graceful close |
| Recipient replies positively | Routed to Ahmed | Ahmed confirms cal.com + WhatsApp |
| Baian unavailable / can't route to cloud | WhatsApp sends held | Ahmed falls back to email (Snov→Zoho) only |
| Agent model produces malformed JSON | Scripted fallback (direct Python) | Ahmed notes in dashboard |

---

## Role Boundary (planning vs. scripting)

This repo/session is **planning only** — templates, specs, docs. All
executable work (enrichment, verification, sending, import, the scoring
pipeline) is done by a **separate scripting model** from a written spec.

- If you are the **scripting/execution** model, your spec is:
  - `05_lead_scoring_model.md` (lead scoring)
  - `agents/lina_marketing.md` (outreach copy) + `agents/tariq_sdr_lead_fetcher.md` → "Outbound Sending"
  - `04_outreach_templates.md` (content)
- If you are a **planning** session, don't write scripts — hand executable work off.
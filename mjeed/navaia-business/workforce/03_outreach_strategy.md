# 03 — Outreach Strategy

> **Status:** design phase. Planning only — sending, personalization-fill, and
> scheduling are handed to the scripting model. See `04_outreach_templates.md`
> for the actual content and `05_lead_scoring_model.md` for prioritization.

**Product context:** Navaia — SaaS for missed-appointment / inquiry recovery
and customer-response automation.

**Verticals:** the 5 from §5.1 (NOT generic). Tier 1: Contracting/Facilities,
Finance & Debt Collection, Private Specialty Clinics. Tier 2: Real Estate,
Training Institutes.

---

## Decisions Locked (from user, 2026-07-06)

| Dimension | Decision |
|-----------|----------|
| **Tone** | Formal فصحى but **direct / brief** — value fast, short paragraphs, warm honorific greeting, no government-letter clichés. |
| **Cadence** | Sequence: day 0 / +3 / +7. (Optionally stretch to +10/+17 — proposed, not yet approved.) |
| **Channel** | Email first; WhatsApp later (via Baian once unblocked). For high-priority leads, manual sends are acceptable. |
| **Targeting** | Not executive-only. Leads are matched to the company's current need (warm/inbound-matched, not pure cold). Target the lead's most-responsive channel / most likely respondent, whoever that is. |
| **CTA placement** | cal.com link + short brief go in **touch 1** (not gated behind a reply). Override of research rec — deliverability offset: warmed domain + plain-text link. |

---

## Outreach Doctrine (adopted 2026-07-08 — HubSpot inbound, adapted)

**Philosophy — human, helpful, holistic.** First contact isn't to sell or demo; it's to
confirm the lead has a problem we can help with and earn a short exploratory call. Lead with
*their* context; be a human helping a human.

**Hard rules (enforced in every email — see `04` conventions):**
- **Reference the buyer ≥ 2× as much as yourself** (count "you/your" vs "we/NAVAIA/I"). Name
  NAVAIA at most once per email.
- **End every email with ONE question on its own line**, asking for ~15 minutes.
- **< 200 words** per email; WhatsApp shorter.
- **Subject = the goal/pain in ≤ 3 words / < 30 chars.**
- **≤ 5 touchpoints** — returns diminish after 5.
- Personalize to the **person**, not the persona. **No mail-merge blasts** (buyers detect them).

**Our outbound adaptation (we're not inbound yet):** HubSpot assumes web-tracked inbound
leads + phone. We source cold via Google Places, with email + WhatsApp (no phone agent). The
lesson's bridge for "not enough inbound leads" is our playbook:
- **Trigger events = our inbound substitute** — open on a real signal (new branch, hiring
  reception/CS, reviews citing "no reply", tenders). Sourced by `scripts/enrich_reviews.py`
  — **trust-locked** to the lead's own Google reviews (exact `place_id` + phone match, never a
  name search) → written to the exact CRM lead → surfaced as `{trigger_line}` in templates.
  Also feeds `05_lead_scoring_model.md`.
- **WhatsApp = "connect live"** (conversational, phone-like).
- **Free consultation, not a demo**, as the personalized offer.
- **Speed-to-lead:** reply to any response within minutes (their data: 21× qualify / 10×
  connect within 5 min) — and it's a live proof of exactly what NAVAIA sells.
- **cal.com** is the meeting-scheduler tool the lesson recommends; it's our soft close, phrased
  as the closing question.

**Reserved for future inbound:** once the website captures leads, the `{inbound_context}` slot
(currently inactive) opens each email on the lead's own action.

---

## Identity (resolved 2026-07-06)

| Field | Value |
|-------|-------|
| **Name** | عبدالمجيد الوردي / Abdulmajeed Alwardi |
| **Role** | تطوير الأعمال / Business Development |
| **Company** | نڤايا / NAVAIA |
| **Phone** | `NAVAIA_CONTACT_PHONE` (see .env) |
| **cal.com** | https://cal.com/abdulmajeed-alwardi |
| **Email** | ops@navaia.sa |

---

## Per-Vertical Value Props

| Vertical (tier) | Arabic value prop | Compliance line |
|-----------------|-------------------|-----------------|
| المقاولات والصيانة وإدارة المرافق (T1) Contracting/Facilities | نڤايا تلتقط طلبات العروض والاستفسارات وتردّ عليها فوراً وتتابع العروض حتى الترسية، فلا يضيع عقد بسبب تأخّر الردّ. | PDPL + أنظمة العمل |
| التمويل والتقسيط ومكاتب التحصيل (T1) Finance & Debt Collection | نڤايا تتابع المتعثّرين بانتظام ووفق أنظمة ساما وحماية البيانات، فيرتفع التحصيل دون إرهاق فريقكم. | **ساما (SAMA)** + PDPL |
| العيادات الخاصة (T1) Private Specialty Clinics (dental/derm/cosmetic/physio) | نڤايا تردّ على استفسارات المرضى وتؤكّد المواعيد وتتابع المتأخّرين، فيبقى الجدول ممتلئاً دون عبء على فريقكم. | **وزارة الصحة (MoH)** + PDPL |
| العقار وإدارة الأملاك (T2) Real Estate | نڤايا تردّ على المهتمّين خلال ثوانٍ قبل أن يبردوا، وتتابع تحصيل الإيجارات في وقتها، فلا تضيع صفقة ولا دفعة. | PDPL + الأنظمة العقارية (REGA) |
| معاهد التدريب (T2) Training Institutes | نڤايا تستوعب زحام موسم التسجيل وتردّ على كل مستفسر في حينه وتتابع الفرص حتى التسجيل، فلا يضيع طالب ولا فرصة. | PDPL + أنظمة التدريب (TVTC) |

---

## Inbound-Sales Research Findings (condensed)

Full brief captured from research; key operating rules for the templates:

- **Sequence beats single touch decisively** — first email captures ~58% of
  eventual replies; follow-ups the other ~42%. Multi-touch roughly doubles
  total responses. Each touch must add a **new angle** (new proof/pain
  framing), not just "bumping" the thread.
- **Reply-rate baselines:** ~3.4% platform avg, 5–10% solid, 10–15%
  excellent, 15%+ best-in-class on tight segments. (Global baselines — Gulf-
  specific public data is thin; instrument our own.)
- **Personalization:** one specific, researched opening line beats a
  paragraph. Keep the whole email **6–8 sentences max** (13+ nearly halves
  reply rate). Reference-line priority for our verticals: (1) concrete
  vertical pain point, (2) their booking/inquiry channel observation, (3)
  location, (4) recent news (only if it exists — don't force it). Only the
  first 1–2 lines are per-lead.
- **Subject lines:** short (~6 words / <35 chars, renders on mobile),
  specific, question- or benefit-led, ≤1 punctuation mark, business
  name/vertical when possible. Personalized subjects open ~50% more.
  Avoid stiff openers like "بالإشارة إلى الموضوع أعلاه".
- **Cultural norms:** high formality; greeting
  **السلام عليكم ورحمة الله وبركاته**; honorific + name (**أستاذ/أستاذة**
  default, **دكتور** for clinics/doctorates, **المهندس** for engineers).
  Lead with brief respectful framing then value fast. Work week **Sun–Thu**;
  best windows Sun AM and Tue–Wed ~10am–12pm AST (UTC+3); **never
  Fri–Sat**. Ramadan: soften tone, add رمضان مبارك, send early AM or
  post-iftar. WhatsApp is the dominant business channel — email as credible
  cold open, move to WhatsApp on engagement.
- **AI/translation tells to avoid (Arabic):** don't calque English
  marketing-speak ("نأخذ عملك إلى المستوى التالي"), don't start every
  sentence with the same connector (وَ/كما/بالإضافة), don't mix فصحى with
  colloquial, don't over-formalize into government-letter clichés. Vary
  sentence length; native Gulf read-aloud QA on the first line before
  sending.
- **CTA:** soft, interest-based CTA on touch 1 (yes/no ask, e.g. "هل
  تسمحون لي بمشاركة فكرة قصيرة…") — interest CTAs ~12% reply vs ~7% for
  time-asks, and links in a cold email hurt deliverability.
  **User override (2026-07-06):** cal.com link + short brief go in touch 1.
  Send the cal.com link only after a positive reply alongside a WhatsApp
  option. Switch to a hard, specific-slot CTA once they're evaluating
  (~2.5x better at that stage).

---

## Free Decision-Maker + Email Lookup Playbook (condensed)

For a lead with just name + domain + city, fastest **free** path to a named
contact + verified email:

1. **Company website /about + Instagram/X bio** — Saudi SMBs often name the
   owner there. 30 seconds, zero risk.
2. **Google dork LinkedIn for name+title** (manual; read the SERP snippet,
   avoid the authwall). Run both English + Arabic title variants:
   `site:linkedin.com/in "<company>" (manager OR مدير OR owner OR مالك OR founder OR مؤسس)`
3. **Apollo.io free plan** (sign up with a corporate-domain email → ~250/day
   credits vs ~100/mo on gmail) — best single free tool for the email.
4. **Hunter.io free** (25 searches + 50 verifies/mo) — Domain Search reveals
   the company's email pattern; use it to construct `first.last@domain`
   (+ transliteration variants: Mohammed/Mohammad/Muhammad, Abdullah/Abdallah).
5. **Verify** before sending — MyEmailVerifier (~100/day), Hunter (50/mo),
   Verifalia (25/day, has API). **KSA caveat:** many SMBs run catch-all
   mail → "accept-all/unknown" is **not** confirmation; fall back to `info@`
   / phone / WhatsApp.
6. **Fallback name sources:** Maroof (maroof.sa) for e-commerce sellers;
   Google Maps **owner replies to reviews** are often signed; Chambers of
   Commerce for legal name + landline.
7. **Stack free tiers** to stay at $0: Apollo (~unlimited-ish) + Hunter
   (25+50) + Snov (50) + Lusha (70) + MyEmailVerifier (~100/day) =
   hundreds/month.

**Compliance:** LinkedIn — manual public-profile viewing OK, **no
automated scraping** (User-Agreement breach → bans). PDPL — contact people
in professional capacity, prefer business/role addresses, honor opt-outs,
include an Arabic opt-out line on any linked page. Never send to
unverified guesses (spam-trap / reputation risk).

---

## Email Flow (fixed order — applies to all 5 verticals)

1. **Subject = the pain point** — drawn from real info, catchy, short
2. **Open on the pain** that concerns *this* company
3. **What we do** — actions taken, **not the how**. Frame as **حلول
   (solutions), never منصّة (platform)**. Add "works on your behalf, no
   extra load on your team" clause (تعمل إلى جانبكم دون عبء). Use
   "نبدأ من…" phrasing so the single named pain implies broader scope.
4. **Impact with prior clients** — stated as plain fact, no "trust me", no
   hype. **Numbers confirmed across verticals: cost −40%, profit +30%.**
5. **Regulatory assurance** — stated clearly, not overstated (per-vertical
   compliance line)
6. **CTA** — cal.com link + WhatsApp option
7. **Signature** — none in the body; Snov.io auto-appends the account's configured signature
   (reference copy: `assets/email_signature.html`)

---

## Benefit Bank — pick TWO of three per lead

| # | Benefit | Arabic phrasing |
|---|---------|-----------------|
| 1 | Cost minimization | خفض في التكاليف التشغيلية بنسبة 40% |
| 2 | Profit increase | ارتفاع في الأرباح بنسبة 30% |
| 3 | Employee productivity | ارتفاع في إنتاجية الفريق ووقت أكبر للتركيز على العميل الحاضر |

---

## Cadence (locked)

| Touch | Day | Purpose | New angle |
|-------|-----|---------|-----------|
| 1 | Day 0 | First touch | Pain subject → company pain → actions → impact → compliance → link |
| 2 | Day +3 | Follow-up | New angle: proof point or specific number |
| 3 | Day +7 | Breakup | Warm door-open, value restatement |
| Positive reply | Anytime | Convert | Confirm cal.com + WhatsApp option; switch to hard CTA |

**Optional (proposed, not approved):** stretch to +10 / +17.

**Send window:** Sun–Thu, ~10am–12pm AST. **Never Fri–Sat.**

---

## Cultural Norms (Arabic-specific)

- **Greeting:** السلام عليكم ورحمة الله وبركاته
- **Honorific + name:** أستاذ / أستاذة (default), دكتور (clinics/doctorates),
  المهندس (engineers)
- **Positioning:** frame as حلول (solutions), not منصّة (platform) — "platform"
  implies work/onboarding for the reader
- **AI tells to avoid:** no em-dashes, no middot bullets (·/•), no calqued
  English marketing-speak, no government-letter clichés
- **Ramadan variant:** add `رمضان مبارك، أعاده الله عليكم بالخير.` under
  greeting; soften CTA verb; send early AM or post-iftar

---

## Tokens (for personalization)

| Token | Per | Meaning |
|-------|-----|---------|
| `{اسم العيادة}` / `{اسم الشركة}` / `{اسم المعهد}` | lead | Business name — noun adapts per vertical |
| `{honorific+name}` | lead | e.g. حضرة الدكتور فلان / الأستاذ فلان |
| `{القناة}` | lead | Their booking/inquiry channel |
| `{pain_line}` | lead | One concrete observation about that business |
| `{benefit_pair}` | lead | Two of the three benefits above, chosen to fit the lead |

Only `{honorific+name}`, `{اسم العيادة}`, `{pain_line}`, and `{benefit_pair}`
are per-lead. The rest are per-vertical.

---

## Templates Reference (full content in `04_outreach_templates.md`)

- **Vertical 1 (T1):** Contracting, Maintenance & Facilities Management
- **Vertical 2 (T1):** Finance, Installment & Debt Collection
- **Vertical 3 (T1):** Private Specialty Clinics (dental/derm/cosmetic/physio)
- **Vertical 4 (T2):** Real Estate & Property Management
- **Vertical 5 (T2):** Training Institutes

Each vertical has 3 touch templates + subject-line options + field lexicon
+ on-positive-reply variants + Ramadan variant.
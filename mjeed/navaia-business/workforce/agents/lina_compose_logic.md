# Lina — Compose Logic (coupled pain→solution)

> How Lina turns a lead into the one dynamic block the outreach template needs.
> Engine: `scripts/lina_compose.py`. Upstream: `scripts/enrich_reviews.py` (`pain_line`).

---

## The template shape (option B — tightest coupling)

The WhatsApp/email template is **whole on its own**; only ONE slot is dynamic:

```
{{1}} = honorific + name
{{2}} = COUPLED pain→solution block   ← Lina composes this
        (fixed: social-proof + impact +30%/−40% + vertical compliance clause)
{{3}} = business name
{{4}} = cal.com link
{{5}} = signature
```

`{{2}}` always carries **a pain AND the NAVAIA solution that addresses that exact pain**,
as one unit — they can never drift apart. `{{2}}` is always filled (specific *or* general),
so the message is never empty/half.

## The decision — relevance wins, not specificity

The lead's specific pain (`pain_line`, grounded in their own Google reviews) is **not**
auto-preferred. Lina ranks:

1. **Specific** — how well `pain_line` maps to a *known, solvable* pain in the vertical's
   library, plus a small "grounded in real reviews" bonus.
2. **General** — the vertical's dominant pain; constant baseline relevance; keeps the
   message whole.

Higher score wins; its coupled solution rides along. **If the specific pain maps to nothing
solvable (noise / praise / off-topic), the general pair wins** — the safe, whole default.
Tunables: `GENERAL_RELEVANCE=1.0`, `GROUNDED_BONUS=0.6`, `PER_KEYWORD=0.6` (one solid keyword
hit + grounded = 1.2 > 1.0 → specific).

## Two-tier matcher (Arabic morphology is the hard part)

- **Tier 1 — deterministic keywords** (`$0`): inflection-friendly cores, substring match on a
  normalized string (tashkeel stripped, أ/إ/آ→ا, ى→ي, ة→ه). Catches the obvious cases.
- **Tier 2 — cheap-LLM semantic classifier** (`--llm`, ~$0.0004/lead, `qwen3.6-plus`): only
  when Tier 1 finds nothing — maps `pain_line` to a category id or `none`. Robust to
  morphology; `none → general`. This is the OPTIMIZATION.md pattern: deterministic floor,
  escalate only the hard cases.

## Pipeline placement

```
enrich_reviews.py  →  pain_line (per lead, in CRM + CSV)
        ↓
lina_compose.py    →  {{2}} coupled block  (choice + category + score logged)
        ↓
Tariq sends        →  WhatsApp (Baian direct Graph API) / email (Snov→Zoho)
```

The library (5 verticals × 3–4 coupled categories + a general default, each with its exact
Arabic pain + matched solution) lives in `scripts/lina_compose.py::LIBRARY`. Compliance clause
per vertical stays in the fixed template body (clinics MoH+PDPL, contracting PDPL+labor,
finance SAMA+collection+PDPL, real-estate PDPL+REGA, training PDPL+TVTC).

## Verified

`python scripts/lina_compose.py --self-test` (offline, Tier 1) — 7 cases pass: empty→general,
grounded pains→specific+coupled solution, praise→general. `--llm` confirmed: praise → "no
solvable match → general". Best-practice web research (relevance/personalization-at-scale) is
pending a rate-limit reset and will refine weights + the library.

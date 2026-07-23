#!/usr/bin/env python3
"""Scan EVERY operational pain a lead's own Google reviews describe. Counted in code.

    python scripts/review_pains.py --leads-file leads_scraped_compact.json --dry-run
    python scripts/review_pains.py --leads-file pool.json --limit 5 --yes

Replaces the two-snippet keyword approach for leads with enough material. It is the only
step in discovery that spends money, so it prints the plan and the cost and STOPS unless
`--yes` is given. A pipe must never be able to approve a spend.

## Three phases, because a model must never be trusted to count

**Phase 0 — free prefilter.** `distill_scraped_leads.negative_reviews()` drops praise-only
and too-short text even at one star. Under `--min-reviews` survivors the lead returns None
having spent ZERO tokens. A 1-star review reading only "ممتاز" is real (people mis-click,
or are sarcastic) and it reached outreach as a company's sole pain hint on 2026-07-20,
guaranteeing a generic message.

**Phase 1 — the model labels, one call per lead.** Each review INDEPENDENTLY gets a short
English descriptor plus a verbatim quote. The descriptor vocabulary is OPEN: `THEMES` steers
wording so repeats group, but the model is told to invent a descriptor for anything else it
sees. A company's problems do not stop at four names, and capping the taxonomy is what
limited the old pipeline to one or two pains.

**Phase 2 — Python counts and verifies.** Any label whose quote is not literally present in
the source review is discarded as a hallucination (this fired on the first live call,
2026-07-21). Frequencies are computed here, never taken from the model. EVERY pain is kept
and ranked by how many reviewers independently reported it — there is no dominance cutoff,
because a company with three problems should be addressed as having three.

**Phase 3 — synthesis.** One further call turns the counted descriptors into a single
internal sentence covering all of them, weighted by frequency. Quotes are NOT passed to it:
it synthesises from descriptors and counts alone, so no reviewer's words can reach anything
downstream even by accident.

## Relevance is NOT decided here

This module reports what the reviews say. Whether NAVAIA can solve a given pain is decided
by `lina_compose.generate_block`, the only layer that knows the solution catalogue.
Filtering here would discard pains we might later address and would bake a product decision
into the scraping layer.

Dedup matters upstream: `user_reviews_extended` repeats `user_reviews`, so an undeduped
input would inflate a pain's count from ONE unhappy customer. `all_reviews()` merges them.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import distill_scraped_leads as distill   # rebinds stdout at import — keep it FIRST
import nav_env

# A strong model, deliberately not the cheapest. Measured across the whole 233-lead pool the
# difference is ~12 cents, and the stronger model is markedly better at Saudi dialect and —
# the part that matters — at DECLINING to force a match. A cheap model that always finds a
# pain is worse than no model, because every lead then gets confident, wrong copy.
MODEL = nav_env.env("REVIEW_PAINS_MODEL", "qwen/qwen3-235b-a22b") or "qwen/qwen3-235b-a22b"
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

# Reference themes. NOT a closed list — the model may return any short descriptor it sees,
# because a company's real problems do not stop at four names and capping the taxonomy is
# exactly what limited the old pipeline to one or two pains. These are examples that steer
# vocabulary so descriptors group together, not an allowed-values enum.
#
# Relevance is deliberately NOT decided here. The scraper's job is to see everything the
# reviews actually say; deciding which of those pains NAVAIA can solve belongs to the
# composer, which is the only place that knows the solution catalogue. Filtering here would
# throw away a pain we might later be able to address, and would bake a product decision
# into the scraping layer.
THEMES = {
    "no_answer": "nobody answers the phone / calls go unanswered / unreachable",
    "slow_reply": "replies are slow, long waits for a response",
    "no_followup": "no follow-up, promised to call back and never did",
    "missed_enquiry": "enquiry or booking request went unanswered / was lost",
}

# Complaints that are real but NOT ours to solve. Named in the prompt because each one has
# actually been mislabelled as a response-time pain during development of this pipeline.
NOT_OUR_PAIN = (
    "price or fees being too high", "land or property measurement disputes",
    "refunds and deposits", "rude or unprofessional staff behaviour",
    "the quality of the property or the work itself", "legal or ownership disputes",
)

# Rough price per 1M input tokens for the default model, USD. Used ONLY to print an estimate
# before spending; it is not billing truth.
USD_PER_MTOK = float(nav_env.env("REVIEW_PAINS_USD_PER_MTOK", "0.20") or 0.20)


def estimate_tokens(reviews: list[str]) -> int:
    """~1 token per 3 chars is a fair rule for mixed Arabic/English, plus prompt overhead."""
    return int(sum(len(r) for r in reviews) / 3) + 400


def build_prompt(name: str, reviews: list[str]) -> str:
    themes = "\n".join(f'  - "{k}": {v}' for k, v in THEMES.items())
    numbered = "\n".join(f"[{i}] {r}" for i, r in enumerate(reviews))
    return (
        f"You are reading customer reviews of a Saudi company called {name} to build an "
        f"internal picture of every operational problem its customers report.\n\n"
        f"For EACH review independently, return a SHORT English descriptor (2-6 words, "
        f"lowercase, snake_case) naming the problem it describes, or \"none\" if the review "
        f"describes no problem at all (praise, a bare rating, off-topic chatter).\n\n"
        f"Reuse these descriptors when they fit, so that repeated problems group together:\n"
        f"{themes}\n"
        f"If a review describes a real problem that none of the above name, INVENT a new "
        f"descriptor in the same style. Do not force a review into a listed descriptor, and "
        f"do not stop at the listed ones — report every distinct problem you actually see.\n\n"
        f"Rules:\n"
        f"1. Judge each review on its own. Do not let one review influence another.\n"
        f"2. For any descriptor other than \"none\" you MUST copy a short VERBATIM quote "
        f"from that review, character for character, in its original language. Do not "
        f"translate, paraphrase, correct spelling, or invent text.\n"
        f"3. Describe the problem neutrally. Do not editorialise or judge the company.\n"
        f"4. Do not count, rank or summarise. Label only.\n\n"
        f"Reviews:\n{numbered}\n\n"
        f'Return ONLY JSON: {{"labels":[{{"i":0,"label":"none","quote":""}}, ...]}} '
        f"with exactly one entry per review, in order."
    )


def build_synthesis_prompt(name: str, ranked: list[dict]) -> str:
    """Turn the counted pain descriptors into ONE internal statement holding all of them.

    Deliberately English and deliberately internal: it is the composer's input, not copy.
    Quotes are NOT passed — the model synthesises from descriptors and counts only, so no
    reviewer's words can survive into anything downstream even by accident. That is what
    makes "never cite reviews" structural rather than a matter of careful prompting.
    """
    lines = "\n".join(f"  - {p['pain']} (reported by {p['count']} of {p['reviewed']} "
                      f"reviewers)" for p in ranked)
    return (
        f"Internal analysis notes for a Saudi company, {name}. Its customers report these "
        f"operational problems:\n{lines}\n\n"
        f"Write ONE plain-English sentence (max 45 words) stating what this company "
        f"struggles with operationally, covering ALL the problems above, weighted so the "
        f"most frequently reported come first.\n\n"
        f"Rules:\n"
        f"- State it as the company's operational situation, not as customer feedback.\n"
        f"- Never mention reviews, ratings, reviewers, customers complaining, or any "
        f"source. Do not say 'customers report' or 'reviewers say'.\n"
        f"- No quotes, no names, no numbers of reviewers.\n"
        f"- Neutral and factual. Do not sell anything and do not propose a solution.\n\n"
        f"Return ONLY JSON: {{\"summary\":\"...\"}}"
    )


def call_model(prompt: str, key: str, timeout: int = 120,
               model: str | None = None, label: str = "review_pains") -> dict | None:
    """Return the model's parsed JSON OBJECT, or None on any failure.

    Returns the whole object rather than one field because several prompts use this: the
    per-review labeller (`{"labels":[...]}`), the synthesiser (`{"summary":"..."}`) and the
    vertical qualifier in `lead_qualify.py`. None always means FAILURE, never "nothing
    found" — a dead key must never be readable as a clean verdict.

    `model` and `label` exist so other judgement steps can share this plumbing rather than
    copy it: `label` only prefixes the failure lines, so a qualification failure does not
    print itself as a review_pains one.
    """
    body = json.dumps({"model": model or MODEL, "temperature": 0.0,
                       "messages": [{"role": "user", "content": prompt}]}).encode()

    # There is ONE OpenRouter key now. The dead second key (MY_OPENROUTER_KEY) was removed
    # from .env on 2026-07-22, and with it the fallback chain that tried it FIRST — which
    # is what made every LLM step fail on a credential rather than on its own logic. The
    # fallback is deliberately not replaced: a 401 now means the real key has a real
    # problem, and silently trying another one is exactly what hid this for a week.
    candidates = list(dict.fromkeys([k for k in (key, nav_env.openrouter_key()) if k]))
    last = None
    for i, cand in enumerate(candidates):
        req = urllib.request.Request(ENDPOINT, data=body,
                                     headers={"Authorization": f"Bearer {cand}",
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                txt = json.load(r)["choices"][0]["message"]["content"]
            break
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 401 and i + 1 < len(candidates):
                print(f"    {label}: key rejected (401) — trying the other "
                      "OpenRouter key. FIX .env: one of the two keys is dead.")
                continue
            print(f"    {label}: model call FAILED (HTTPError {e.code}: {e.reason})")
            return None
        except Exception as e:  # noqa: BLE001
            # FAILURE must be distinguishable from "no pain found". Returning None-as-no-pain
            # would let a dead key or a rate limit look like a clean, confident verdict.
            print(f"    {label}: model call FAILED ({type(e).__name__}: {e})")
            return None
    else:
        print(f"    {label}: all OpenRouter keys rejected ({last})")
        return None
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        print(f"    {label}: model returned no JSON object")
        return None
    try:
        parsed = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        print(f"    {label}: unparseable JSON ({e.msg})")
        return None
    return parsed if isinstance(parsed, dict) else None


def _norm(s: str) -> str:
    """Whitespace-insensitive comparison. Nothing else is normalised: the quote must be the
    model's own copy of real text, not something we massaged into matching."""
    return re.sub(r"\s+", " ", (s or "")).strip()


def _norm_label(label: str) -> str:
    """Fold descriptor spelling so 'no answer', 'No_Answer' and 'no-answer' group as one."""
    return re.sub(r"[\s\-]+", "_", (label or "").strip().lower()).strip("_")


def verify(labels: list[dict], reviews: list[str]) -> tuple[list[tuple[str, str]], int]:
    """Keep only labels whose quote literally appears in the review it was assigned to.

    Returns (verified pairs, hallucinated count). A quote the model invented is the one
    failure that would otherwise flow all the way into Arabic outreach copy as if a
    customer had written it. Verified live on 2026-07-21: the model produced exactly such a
    quote on the first real call and this discarded it.

    Descriptors are open-ended — anything the model saw is kept, because the scraper is not
    the place that decides which pains we can address.
    """
    verified: list[tuple[str, str]] = []
    hallucinated = 0
    for entry in labels:
        if not isinstance(entry, dict):
            continue
        label = _norm_label(str(entry.get("label") or "none"))
        if label in ("none", ""):
            continue
        try:
            idx = int(entry.get("i"))
        except (TypeError, ValueError):
            hallucinated += 1
            continue
        if not 0 <= idx < len(reviews):
            hallucinated += 1
            continue
        quote = _norm(entry.get("quote") or "")
        if not quote or quote not in _norm(reviews[idx]):
            hallucinated += 1
            continue
        verified.append((label, quote))
    return verified, hallucinated


def pain_profile(lead: dict, key: str | None = None, min_reviews: int = 3,
                 verbose: bool = True) -> dict | None:
    """EVERY operational pain this lead's reviews describe, counted, plus one summary.

    Returns `{"pains": [{pain, count, reviewed, share}, ...], "summary": str,
    "reviewed": int}` or None when there is nothing evidenced.

    Deliberately NOT a single dominant theme. Capping at one pain is what made the old
    pipeline generic: a company that is slow to answer AND loses follow-ups AND drops
    booking requests has three problems, and describing one of them makes the outreach
    read as a lucky guess rather than as understanding their business.

    Nothing is filtered for relevance here. The composer owns that decision because it is
    the only layer that knows what NAVAIA actually solves.
    """
    reviews = lead.get("negative_reviews")
    if reviews is None:
        # Pool files distilled before 2026-07-21 lack the full text. Fall back to whatever
        # review data the row carries so an old pool degrades rather than crashing.
        reviews = [rv["Description"] for rv in distill.negative_reviews(lead)]
    reviews = [r for r in (reviews or []) if r and r.strip()]

    if len(reviews) < min_reviews:
        if verbose:
            print(f"    prefilter: {len(reviews)} usable negative reviews "
                  f"(< {min_reviews}) — no spend, no pain claimed")
        return None
    if not key:
        if verbose:
            print("    no API key — cannot reason; returning None (NOT 'no pain')")
        return None

    payload = call_model(build_prompt(lead.get("name", "?"), reviews), key)
    if payload is None:
        return None
    labels = list(payload.get("labels") or [])

    verified, hallucinated = verify(labels, reviews)
    if hallucinated and verbose:
        print(f"    discarded {hallucinated} label(s): quote not present in the review")
    if not verified:
        if verbose:
            print("    no verified pain in these reviews")
        return None

    # Counted HERE, never taken from the model. Every pain is kept, ranked by how many
    # reviewers independently reported it — the composer needs the weighting, not a cutoff.
    counts = Counter(lbl for lbl, _ in verified)
    ranked = [{"pain": lbl, "count": n, "reviewed": len(reviews),
               "share": round(n / len(reviews), 3)}
              for lbl, n in counts.most_common()]

    summary = ""
    synth = call_model(build_synthesis_prompt(lead.get("name", "?"), ranked), key)
    if synth:
        summary = str(synth.get("summary") or "").strip()
    if not summary:
        # Synthesis is a convenience for the gate and for the composer's prompt. If it
        # fails, the counted descriptors are still the real product — degrade, do not lose.
        summary = "; ".join(f"{p['pain'].replace('_', ' ')} ({p['count']})" for p in ranked)
        if verbose:
            print("    synthesis unavailable — using the counted descriptor list")

    if verbose:
        print(f"    {len(ranked)} distinct pain(s) across {len(reviews)} reviews: "
              + ", ".join(f"{p['pain']}×{p['count']}" for p in ranked[:6]))

    return {"pains": ranked, "summary": summary, "reviewed": len(reviews),
            "quotes_internal": [q for _, q in verified][:6]}


def dominant_theme(lead: dict, key: str | None = None, min_reviews: int = 3,
                   min_count: int = 2, min_share: float = 0.25,
                   verbose: bool = True) -> dict | None:
    """Back-compat shim: the single most-reported pain, thresholded as before.

    `discover.py` and anything else expecting the old single-theme contract keep working.
    New callers should use `pain_profile`, which does not throw away the other pains.
    """
    profile = pain_profile(lead, key, min_reviews, verbose=verbose)
    if not profile or not profile["pains"]:
        return None
    top = profile["pains"][0]
    if top["count"] < min_count or top["share"] < min_share:
        return None
    return {"theme": top["pain"], "description": THEMES.get(top["pain"], top["pain"]),
            "count": top["count"], "reviewed": top["reviewed"], "share": top["share"],
            "quotes": profile["quotes_internal"][:3], "summary": profile["summary"]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--leads-file", default="leads_scraped_compact.json")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--min-reviews", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true",
                    help="prefilter + cost estimate only; never calls the model")
    ap.add_argument("--yes", action="store_true",
                    help="authorise the spend. Without it this prints the plan and stops.")
    args = ap.parse_args()

    with open(args.leads_file, encoding="utf-8") as f:
        data = json.load(f)
    leads = data.get("leads", data) if isinstance(data, dict) else data
    if args.limit:
        leads = leads[:args.limit]

    # Phase 0 across the whole set FIRST, so the printed cost is what will actually be spent.
    eligible, tokens = [], 0
    for lead in leads:
        reviews = lead.get("negative_reviews")
        if reviews is None:
            reviews = [rv["Description"] for rv in distill.negative_reviews(lead)]
        reviews = [r for r in (reviews or []) if r and r.strip()]
        if len(reviews) >= args.min_reviews:
            eligible.append((lead, reviews))
            tokens += estimate_tokens(reviews)

    cost = tokens / 1_000_000 * USD_PER_MTOK
    print(f"leads:            {len(leads)}")
    print(f"eligible (>= {args.min_reviews} usable negative reviews): {len(eligible)}")
    print(f"model:            {MODEL}")
    print(f"estimated input:  ~{tokens:,} tokens  ->  ~${cost:.3f}")

    if args.dry_run:
        print("\nDRY RUN — no model calls made.")
        return 0
    if not eligible:
        print("\nNothing eligible. No spend.")
        return 0
    if not args.yes:
        # The standing rule: print the plan and the cost, then STOP. Never spend on our own
        # initiative, and never let a pipe approve it — hence a flag, not a prompt.
        print("\nNot spending without --yes. Re-run with --yes to authorise.")
        return 0

    key = nav_env.openrouter_key()
    if not key:
        print("\nNo OPENROUTER_API_KEY — refusing to continue.")
        return 1

    found = 0
    for i, (lead, _) in enumerate(eligible, 1):
        print(f"[{i}/{len(eligible)}] {lead.get('name','?')}")
        result = dominant_theme(lead, key, args.min_reviews)
        if result:
            found += 1
            print(f"    -> {result['theme']} {result['count']}/{result['reviewed']} "
                  f"(share {result['share']}) : {result['quotes'][0][:70]}")
    print(f"\ndominant pain found for {found}/{len(eligible)} eligible leads")
    return 0


if __name__ == "__main__":
    sys.exit(main())

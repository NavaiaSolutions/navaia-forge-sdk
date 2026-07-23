#!/usr/bin/env python3
"""The single entry point Rashid calls. One lead finished completely, then the next.

    python scripts/discover.py --limit 3 --dry-run
    python scripts/discover.py --source pool --leads-file leads_scraped_compact.json
    python scripts/discover.py --source osm --verticals "Real Estate"

## Shape

Per lead, in order, resumable at every boundary:

    1 identity    name, phone, address, website, place_id     candidate source
    2 reviews     ranked recurring pains                      review_pains (optional)
    3 site        emails, headcount, opener facts             site_facts + enrich_company_size
    4 people      named contacts + roles                      people_facts
    5 write       company + person, fully enriched            crm_write (upsert)
    6 checkpoint  mark done, flush state

## Why an LLM does not drive this loop

Deployed agents cap at `max_turns=25`. A model stepping a 200-lead pool would exhaust its
turns partway and stop mid-pool, having reported success for the leads it did reach. The
agent's job is to run this file; the loop lives in Python where it can be resumed, counted
and audited. That is the script-authority rule from `workforce/POSTMORTEM_2026-07-14.md`.

## Why the candidate source is an argument

Steps 2-5 are ordinary HTTP against a company's own public site and run anywhere. Step 1 is
not: Maps discovery needs the `google-maps-scraper` binary, and scraping Maps from a
datacenter IP is far more likely to be blocked than from a laptop. So the source is
pluggable — a local pool file, a fresh gosom run, or the keyless OSM fallback — and the rest
of the pipeline does not change when that decision changes.

## Resumability

State lives in `discovery_state.json` via `polite_fetch.load_store/save_store`, which merge
then atomically replace. A killed run loses at most the lead in flight. Do NOT swap this for
a plain json.dump: a plain dump destroyed 16 credits of results twice on 2026-07-20.
Page fetches are additionally cached by `PageCache`, so a re-run re-pays parsing but never
the 12-second-per-host politeness delay.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import time
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import nav_env
import polite_fetch
import site_facts
import people_facts
import crm_write
import enrich_emails_crawl4ai
import distill_scraped_leads as distill

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
STATE_PATH = os.path.join(polite_fetch.state_dir(), "discovery_state.json")

# Locked to three by operator decision 2026-07-19. Retired verticals are never scraped,
# scored, imported, composed for, or sent to.
ACTIVE_VERTICALS = ["Real Estate", "Contracting & Facilities", "Training Institutes"]

# Pages worth fetching per lead, in priority order. The budget is a politeness budget as
# much as a time one: at 12s/host, ten pages is two minutes of sleeping.
SITE_PATHS = ["", "about", "about-us", "contact", "contact-us", "من-نحن", "اتصل-بنا"]

# Directory/portal hosts that a Maps listing often gives as "website". They are NOT the
# company's own site, and treating them as one is wrong twice over: the crawl finds the
# portal's boilerplate instead of the company's facts, and `aqar.fm/user/900056` gets
# written into the CRM as that company's domain. Found in a live dry run 2026-07-21.
# Extend with DISCOVER_PORTAL_HOSTS (comma-separated) rather than editing this list.
PORTAL_HOSTS = {
    "aqar.fm", "sa.aqar.fm",          # Saudi property portal — the common case
    "maps.google.com", "goo.gl", "g.page",
    "facebook.com", "m.facebook.com", "instagram.com", "twitter.com", "x.com",
    "linkedin.com", "wa.me", "api.whatsapp.com", "t.me", "snapchat.com", "tiktok.com",
    "youtube.com", "linktr.ee", "bit.ly",
}
PORTAL_HOSTS |= {h.strip().lower()
                 for h in (nav_env.env("DISCOVER_PORTAL_HOSTS", "") or "").split(",")
                 if h.strip()}


def is_portal_lead(lead: dict) -> bool:
    """True when the lead's whole web presence is a portal/social listing.

    Operator rule (2026-07-21): **a portal is not a prospect.** Two distinct cases collapse
    into this one check, and both are correct to drop:

      * The record IS an aggregator (`aqar.fm`, a Linktree) rather than a company we sell to.
      * The record is a real company reachable only through someone else's platform, so
        there is no site to enrich, no team page, no email — the discovery pipeline has
        nothing to add beyond the phone the scrape already had.

    Skipping is decided BEFORE any fetch, so a portal lead costs no crawl budget and no
    CRM round-trip. Override with --keep-portal-leads if a batch needs them anyway.
    """
    raw = (lead.get("website") or "").strip()
    if not raw:
        return False          # no website at all is not a portal — it is just unknown
    return not own_website(lead)


def own_website(lead: dict) -> str:
    """The company's OWN site, or '' when all we have is a portal/social listing.

    Returning '' is the honest answer: we do not know this company's website. A blank
    field is correct and never overwrites an established value downstream, whereas a
    portal URL is an actively wrong one.
    """
    raw = (lead.get("website") or "").strip()
    if not raw:
        return ""
    host = crm_write.norm_host(raw)
    if host in PORTAL_HOSTS or any(host.endswith("." + p) for p in PORTAL_HOSTS):
        return ""
    return raw


# ── candidate sources ────────────────────────────────────────────────────────────────

def source_pool(path: str) -> list[dict]:
    """Leads distilled from a gosom scrape. The default, and the only rich source."""
    if not os.path.exists(path):
        raise SystemExit(f"No lead pool at {path}. Run distill_scraped_leads.py first, "
                         f"or pass --source osm.")
    with io.open(path, encoding="utf-8") as f:
        data = json.load(f)
    leads = data.get("leads", data) if isinstance(data, dict) else data
    return [l for l in leads if isinstance(l, dict)]


# The Maps queries per vertical. Riyadh only, Arabic — the same search terms the old Places
# flow used. Kept here rather than in a data file so a cloud run needs no extra mount.
GMAPS_QUERIES = {
    "Real Estate": ["مكتب عقاري الرياض", "شركة عقارية الرياض", "إدارة أملاك الرياض"],
    "Contracting & Facilities": ["شركة مقاولات الرياض", "إدارة مرافق الرياض",
                                 "شركة تشغيل وصيانة الرياض"],
    "Training Institutes": ["معهد تدريب الرياض", "مركز تدريب أهلي الرياض"],
}

# Riyadh centre, and the settings proven on 2026-07-14 (32 places incl. Arabic reviews from
# one query). Concurrency and depth stay LOW on purpose: heavy scraping risks a block and
# violates Google's ToS, and the budget here is fit quality, not lead count.
GMAPS_GEO, GMAPS_ZOOM, GMAPS_DEPTH, GMAPS_CONCURRENCY = "24.7136,46.6753", "12", "3", "2"


def source_gmaps(verticals: list[str], binary: str, out_dir: str,
                 depth: str = GMAPS_DEPTH) -> list[dict]:
    """Run the google-maps-scraper binary and return distilled leads.

    This is the step that makes discovery self-contained in the cloud. Until now `--source
    pool` required a `leads_scraped_compact.json` produced by a human running gosom under
    Docker on a laptop — a file that does not exist at /app/workspace and cannot be created
    there, because the runtime is an unprivileged uid with no Docker socket. So the cloud
    could only ever use `--source osm`, which is ~30 phoned POIs with no reviews, and the
    review-grounded pain that the whole composer depends on was unreachable.

    `deploy/discovery/Dockerfile` already lifts the binary onto PATH for exactly this. It
    was shipped; nothing called it.

    Fails CLOSED and loudly when the binary is absent: a discovery step that cannot scrape
    must report that, never return an empty list that reads like "no businesses matched".
    """
    if not shutil.which(binary) and not os.path.exists(binary):
        raise SystemExit(
            f"google-maps-scraper not found (looked for {binary!r}). This runtime cannot "
            f"scrape Maps. Use --source osm for the keyless fallback, or --source pool with "
            f"a file. NOT returning an empty result set: that is indistinguishable from a "
            f"search that legitimately found nothing.")

    queries = [q for v in verticals for q in GMAPS_QUERIES.get(v, [])]
    if not queries:
        raise SystemExit(f"No Maps queries defined for {verticals}.")

    os.makedirs(out_dir, exist_ok=True)
    qpath = os.path.join(out_dir, "queries.txt")
    rpath = os.path.join(out_dir, "leads_raw.json")
    with io.open(qpath, "w", encoding="utf-8") as f:
        f.write("\n".join(queries) + "\n")

    cmd = [binary, "-input", qpath, "-results", rpath, "-json", "-extra-reviews",
           "-depth", depth, "-c", GMAPS_CONCURRENCY, "-geo", GMAPS_GEO, "-lang", "ar",
           "-zoom", GMAPS_ZOOM, "-exit-on-inactivity", "3m"]
    print(f"    scraping {len(queries)} queries -> {rpath}")
    # No shell: the query strings are data and must never be parsed as a command line.
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    if proc.returncode != 0 and not os.path.exists(rpath):
        raise SystemExit(f"google-maps-scraper failed (exit {proc.returncode}): "
                         f"{(proc.stderr or '')[-400:]}")

    rows = distill.read_records(rpath)
    leads = [distill.normalise(r) for r in rows]
    print(f"    scraped {len(leads)} listings")
    return [l for l in leads if isinstance(l, dict) and l.get("name")]


def source_osm(verticals: list[str]) -> list[dict]:
    """Keyless fallback. Thin (~30 phoned Riyadh POIs) but it runs anywhere, including a
    cloud runtime with no browser — verified reachable from the cloud on 2026-07-21."""
    import fetch_leads_osm
    rows = fetch_leads_osm.collect() if hasattr(fetch_leads_osm, "collect") else []
    if not rows:
        print("OSM source returned nothing. It is a thin supplement, not a primary — "
              "this is a normal result, not an error.")
    return [r for r in rows if not verticals or r.get("sector") in verticals]


def load_candidates(args) -> list[dict]:
    if args.source == "osm":
        return source_osm(args.verticals)
    if args.source == "gmaps":
        return source_gmaps(args.verticals, args.gmaps_binary,
                            args.gmaps_out or polite_fetch.state_dir(), args.gmaps_depth)
    return source_pool(args.leads_file)


# ── per-lead steps ───────────────────────────────────────────────────────────────────

def _llm_key() -> str | None:
    """OpenRouter key, via the one accessor. See nav_env.openrouter_key."""
    return nav_env.openrouter_key()


def lead_key(lead: dict) -> str:
    """Stable identity for state. place_id is exact; phone is the cross-source fallback."""
    return ((lead.get("place_id") or "").strip()
            or crm_write.norm_phone(lead.get("phone") or "")
            or crm_write.norm_name(lead.get("name") or ""))


def step_qualify(lead: dict, spend: bool, key: str | None = None) -> dict:
    """Confirm the lead IS one of the three active verticals. Judgement, not keywords.

    Runs FIRST, before reviews and before any crawl, for two reasons. A lead we are going to
    drop should not cost a paid pain extraction or six polite page fetches. And a
    mis-verticalized lead is the expensive error downstream: it receives real Arabic outreach
    about a pain it does not have, under the operator's name.

    Returns {} when nothing changes, so the caller's `record.update()` is a no-op on the
    fallback path. See lead_qualify for why failure keeps the keyword guess.
    """
    guess = vertical_of(lead)
    try:
        import lead_qualify
    except ImportError:
        return {}
    verdict = lead_qualify.qualify(lead, guess, key, spend=spend)
    sector, src = verdict["sector"], verdict["source"]
    if src in ("llm",) and sector != guess:
        print(f"    qualify: {guess or '(none)'} -> {sector or 'DROP'} ({verdict['reason']})")
    elif src == "error":
        print(f"    qualify: {verdict['reason']}")
    # `sector` is authoritative from here on: vertical_of() reads it before sector_guess.
    return {"sector": sector, "qualify_reason": verdict["reason"],
            "qualify_source": src}


def step_reviews(lead: dict, spend: bool, key: str | None = None) -> dict:
    """EVERY pain the lead's own reviews describe, counted, plus one internal summary.

    Optional: `review_pains` is the only step that costs money. Absent module or no --llm
    degrades to whatever the distiller already extracted.

    Nothing is filtered for relevance here, and no pain is dropped for being less frequent
    than another. The composer decides what NAVAIA can address, because it is the only
    layer that knows the solution catalogue — see `lina_compose.generate_block`. A lead with
    no evidenced pain carries none; the composer still produces publishable copy from the
    vertical's general block, so an empty profile costs nothing downstream.
    """
    if not spend:
        return {"pain_hints": lead.get("pain_hints") or []}
    # --llm is ON by default now, so "no key" is a configuration mistake rather than a
    # deliberate choice, and it must be loud. Silently degrading here is what made the dead
    # MY_OPENROUTER_KEY invisible for a week: every lead fell back to keyword hints and the
    # run still reported success.
    if not key:
        print("    !! reviews: no OPENROUTER_API_KEY — pain extraction SKIPPED, "
              "falling back to keyword hints (copy will be generic)")
        return {"pain_hints": lead.get("pain_hints") or []}
    try:
        import review_pains
    except ImportError:
        print("    reviews: review_pains.py not present — keeping distilled hints")
        return {"pain_hints": lead.get("pain_hints") or []}

    profile = review_pains.pain_profile(lead, key)
    if not profile:
        return {"pain_hints": []}
    return {
        # The composer's real input. Quotes are NOT carried: they exist only to prove a
        # label was grounded, and keeping them out of the lead record is what makes
        # "never cite reviews" impossible to violate downstream.
        "pain_summary": profile["summary"],
        "pains": profile["pains"],
        "pain_hints": lead.get("pain_hints") or [],
    }


def step_site(lead: dict, cache: polite_fetch.PageCache, budget: int) -> dict:
    """Emails and opener facts from ONE crawl of the company's own site.

    Email harvest was missing until 2026-07-23: this step called `site_facts.extract`,
    which only reads opener numerics (branches/projects/years) and never emails, so a
    10-lead pilot enriched 0 addresses despite `info@`/`sales@` sitting in plain text on
    the fetched pages. The company mailbox is the single highest-value field the CRM lacks
    for this pool, so it is harvested HERE — from the SAME page text already fetched, at no
    extra crawl cost — using the shared harvester whose portal guard prevents the
    2026-07-21 misdirected send.
    """
    website = own_website(lead)
    if not website:
        return {}
    base = website if website.startswith("http") else "https://" + website
    pages = cache.get_many(base, SITE_PATHS, budget)
    if not pages:
        return {}

    merged = "\n\n".join(pages.values())
    out: dict = {}

    facts = site_facts.extract(merged)
    if facts:
        out["site_facts"] = facts

    domain = urlparse(base).netloc or base
    emails = enrich_emails_crawl4ai.harvest(merged, domain, base)
    if emails:
        out["site_emails"] = emails
        out["site_email"] = emails[0]
    return out


def step_people(lead: dict, cache: polite_fetch.PageCache, budget: int) -> dict:
    """Named contacts from public team/leadership pages. No Snov, by decision."""
    website = own_website(lead)
    if not website:
        return {}
    base = website if website.startswith("http") else "https://" + website
    found = people_facts.from_pages(cache.get_many(base, people_facts_paths(), budget))
    if not found:
        return {}
    # One person per lead for the CRM record: the most senior with a usable contact.
    best = max(found, key=lambda p: (bool(p.get("email")), bool(p.get("role"))))
    return {"person": best, "people_all": found}


def people_facts_paths() -> list[str]:
    paths = getattr(people_facts, "PATHS", None) or getattr(people_facts, "SLUGS", None)
    return list(paths) if paths else ["team", "our-team", "leadership", "management",
                                      "فريق-العمل", "الإدارة", "من-نحن"]


def vertical_of(lead: dict) -> str:
    """The lead's vertical. `distill_scraped_leads` writes `sector_guess`; CRM-shaped
    records carry `sector`. Blank is a legitimate value meaning "unclassified" — the
    distiller leaves it blank rather than guess, and so do we: Twenty requires one of the
    exact vertical names, and inventing one to satisfy the schema would put a fabricated
    classification into the shared CRM."""
    return (lead.get("sector") or lead.get("sector_guess") or "").strip()


# Scrape facts that the CRM has NO field for, audited against the live schema 2026-07-22.
# The metadata API that would let us create fields answers 403 PERMISSION_DENIED for this
# key, so these cannot be pushed to Twenty however much we would like them there.
#
# They are checkpointed here instead, keyed by place_id, for one specific reason: the
# operator wants to delete `leads_scraped_compact.json` once the CRM is enriched, and
# `pain_hints` is the composer's grounding for 136 leads. Dropping the local file without
# rescuing these would silently degrade every message written for those leads afterwards,
# and nothing downstream would report it — the composer would just quietly fall back to
# the vertical's general pain.
#
# This is a holding pen, not a second CRM. When the metadata permission is granted these
# move to real fields and this goes away.
RESCUE_FIELDS = ("rating", "review_count", "category", "pain_hints", "lead_source")


def rescue_facts(lead: dict) -> dict:
    """The scrape fields Twenty cannot store. Blank/missing values are not recorded."""
    return {k: lead[k] for k in RESCUE_FIELDS
            if lead.get(k) not in ("", None, [], {})}


def step_write(lead: dict, index: list[dict] | None, dry_run: bool,
               known_id: str = "") -> dict:
    vertical = vertical_of(lead)
    if not vertical:
        return {"crm": "skipped", "reason": "unclassified vertical — left for qualification"}
    if vertical not in ACTIVE_VERTICALS:
        return {"crm": "skipped", "reason": f"vertical {vertical!r} not active"}
    company_id, cstate = crm_write.upsert_company(lead, vertical, index, dry_run, known_id)
    if not company_id and not dry_run:
        return {"crm": "failed", "reason": "company upsert returned no id"}
    person_id, pstate = ("", "skipped")
    if company_id or dry_run:
        person_id, pstate = crm_write.upsert_person(lead, vertical, company_id or "", dry_run)
    return {"crm": f"company:{cstate} person:{pstate}",
            "company_id": company_id, "person_id": person_id}


# ── the loop ─────────────────────────────────────────────────────────────────────────

def run(args) -> int:
    candidates = load_candidates(args)
    state = polite_fetch.load_store(STATE_PATH)
    done = state.get("done", {})
    cache = polite_fetch.PageCache()

    # A checkpoint means "done" only for the work that ACTUALLY RAN.
    #
    # `--crm-only` skips reviews/site/people by design, but it wrote the same `done` entry
    # as a full pass. So the cheap sweep of 2026-07-21 marked all 233 leads done, and every
    # full run afterwards computed pending=0 and printed "Nothing to do." — while enrichment
    # had never executed even once. The expensive step was masked by the cheap one, and the
    # run reported success for work it never did.
    #
    # `enriched` records which happened. A full run therefore re-opens a lead that only ever
    # got the CRM sweep, while a `--crm-only` run keeps the old cheap behaviour and re-opens
    # nothing. `--redo` forces everything through regardless.
    def needs_work(lead) -> bool:
        entry = done.get(lead_key(lead))
        if entry is None:
            return True
        if args.redo:
            return True
        if args.crm_only:
            return False
        return not entry.get("enriched", False)

    pending = [l for l in candidates if lead_key(l) and needs_work(l)]
    reopened = sum(1 for l in pending if lead_key(l) in done)
    if args.limit:
        pending = pending[:args.limit]

    print(f"source={args.source}  candidates={len(candidates)}  "
          f"already done={len(done)}  this run={len(pending)}")
    if reopened:
        print(f"  ({reopened} previously checkpointed WITHOUT enrichment — re-opened; "
              f"the CRM write is a non-destructive merge, so this updates rather than "
              f"duplicates)")
    if args.dry_run:
        print("DRY RUN — no CRM writes will be made.\n")
    if not pending:
        print("Nothing to do.")
        return 0

    # One paginated CRM read for the whole run, not one per lead.
    index = None
    if not args.dry_run or args.source != "osm":
        try:
            index = crm_write.all_companies()
            print(f"CRM index: {len(index)} companies\n")
        except Exception as e:  # noqa: BLE001
            print(f"WARN could not read CRM companies ({e}); "
                  f"upserts will resolve per-lead\n")

    started = time.time()
    counts = {"written": 0, "skipped": 0, "failed": 0}

    for i, lead in enumerate(pending, 1):
        key = lead_key(lead)
        if not key:
            print(f"[{i}/{len(pending)}] SKIP — no usable identity (no place_id/phone/name)")
            counts["skipped"] += 1
            continue

        name = lead.get("name", "?")
        print(f"[{i}/{len(pending)}] {name}")

        if not args.keep_portal_leads and is_portal_lead(lead):
            host = crm_write.norm_host(lead.get("website") or "")
            print(f"    -> skipped (portal listing {host!r} — not a prospect)")
            counts["skipped"] += 1
            # Checkpointed as done: the verdict is a property of the lead, not of this run,
            # so re-running must not re-examine it.
            if not args.dry_run:
                done[key] = {"name": name, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                             "crm": "skipped:portal", "company_id": "",
                             # A portal verdict is a property of the lead, not of this
                             # run, so it counts as settled at any enrichment level.
                             "enriched": True,
                             "facts": rescue_facts(lead)}
                polite_fetch.save_store(STATE_PATH, {"done": done})
            continue

        record = dict(lead)
        # Normalise ONCE, before any step reads it: a portal listing is not a website, and
        # the CRM write reads this same field. Without this, `domainName` would be set to
        # the portal URL even though no step ever crawled it.
        record["website"] = own_website(lead)

        try:
            if not args.crm_only:
                # Qualify BEFORE spending: a lead that fails here costs no pain extraction
                # and no crawl. An empty sector makes step_write skip it with a reason.
                record.update(step_qualify(record, spend=args.llm, key=_llm_key()))
                if not vertical_of(record):
                    reason = record.get("qualify_reason") or "not an active vertical"
                    print(f"    -> skipped (qualify: {reason})")
                    counts["skipped"] += 1
                    if not args.dry_run:
                        done[key] = {"name": name,
                                     "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                     "crm": "skipped:qualify", "company_id": "",
                                     "reason": reason, "enriched": True,
                                     "facts": rescue_facts(lead)}
                        polite_fetch.save_store(STATE_PATH, {"done": done})
                    continue
                record.update(step_reviews(lead, spend=args.llm, key=_llm_key()))
                record.update(step_site(record, cache, args.page_budget))
                # The people-crawl is a SECOND pass over the same host with a different path
                # list — it roughly doubles per-lead crawl time. On this pool it yields
                # almost no real names (and a false positive: "التنمية المستدامة"), so
                # --skip-people trades that near-zero yield for ~half the wall-clock. The
                # company mailbox from step_site still lands via the reconcile below.
                if not args.skip_people:
                    record.update(step_people(record, cache, args.page_budget))
                # step_people runs AFTER step_site and REPLACES record["person"], so the
                # site email is reconciled here, once both have run. A named person's OWN
                # address always wins; the company mailbox (info@) fills a person who has
                # none — including the company-as-person placeholder when no human was
                # found — because reaching info@ still reaches the business, and it is the
                # only sendable address this pool yields for most leads.
                if record.get("site_email"):
                    person = record.setdefault("person", {})
                    # NOT setdefault: people_facts ALWAYS writes an "email" key, empty when
                    # it found a named person but no personal address (people_facts.py:234).
                    # setdefault treats that present-but-empty key as "already set" and drops
                    # the company mailbox — which is precisely when we most need it, since a
                    # named contact with no email is otherwise unreachable. Fill on empty.
                    if not (person.get("email") or "").strip():
                        person["email"] = record["site_email"]
            # The company id this place_id resolved to before — stands in for the
            # `placeId` field Twenty does not have. Exact, and free to consult.
            result = step_write(record, index, args.dry_run,
                                (done.get(key) or {}).get("company_id", ""))
        except KeyboardInterrupt:
            print("\nInterrupted — state for finished leads is already flushed.")
            return 130
        except Exception as e:  # noqa: BLE001 — one bad lead must not end the run
            print(f"    ERROR {type(e).__name__}: {e}")
            counts["failed"] += 1
            continue

        print(f"    -> {result.get('crm')}"
              + (f" ({result['reason']})" if result.get("reason") else ""))
        if str(result.get("crm", "")).startswith("company:"):
            counts["written"] += 1
        else:
            counts["skipped"] += 1

        # Checkpoint AFTER the write: a lead is only done once the CRM has it.
        if not args.dry_run:
            done[key] = {"name": name, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                         "crm": result.get("crm", ""),
                         "company_id": result.get("company_id") or "",
                         # False after a --crm-only sweep, so a later full run re-opens
                         # this lead instead of treating the cheap pass as complete.
                         "enriched": not args.crm_only,
                         # See RESCUE_FIELDS: what the CRM schema cannot hold, so that
                         # deleting the local leads file loses nothing.
                         "facts": rescue_facts(lead)}
            polite_fetch.save_store(STATE_PATH, {"done": done})

        if args.max_seconds and (time.time() - started) > args.max_seconds:
            print(f"\nWall-clock budget of {args.max_seconds}s reached — stopping cleanly. "
                  f"Re-run to continue.")
            break

    print(f"\nwritten={counts['written']}  skipped={counts['skipped']}  "
          f"failed={counts['failed']}  pages fetched={cache.fetched_count}  "
          f"elapsed={int(time.time() - started)}s")
    if not args.dry_run:
        print(f"state: {STATE_PATH}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["pool", "gmaps", "osm"], default="pool",
                    help="candidate origin; steps 2-5 are identical either way")
    ap.add_argument("--leads-file",
                    default=os.path.join(ROOT, "leads_scraped_compact.json"))
    ap.add_argument("--gmaps-binary",
                    default=nav_env.env("NAVAIA_GMAPS_BINARY", "google-maps-scraper")
                    or "google-maps-scraper",
                    help="path to the google-maps-scraper binary (--source gmaps). "
                         "The discovery image puts it on PATH.")
    ap.add_argument("--gmaps-out", default="",
                    help="where to write queries.txt and leads_raw.json "
                         "(default: the state dir, so it persists with the checkpoint)")
    ap.add_argument("--gmaps-depth", default=GMAPS_DEPTH,
                    help=f"Maps scroll depth per query (default {GMAPS_DEPTH}). Keep it "
                         f"low: heavy scraping risks a block and violates Google's ToS.")
    ap.add_argument("--verticals", type=lambda s: [v.strip() for v in s.split(",")],
                    default=ACTIVE_VERTICALS)
    ap.add_argument("--limit", type=int, default=0, help="0 = all pending")
    ap.add_argument("--page-budget", type=int, default=6,
                    help="max pages fetched per lead per step (politeness budget)")
    ap.add_argument("--max-seconds", type=int, default=0,
                    help="stop cleanly after N seconds; re-run resumes")
    # ON by default (operator decision 2026-07-22). Review-pain extraction IS the step that
    # turns a listing into a lead the composer can write honestly about: it reads every
    # review and names ALL the pains, where the keyword fallback only ever matched one or
    # two. With it off, discovery silently produced leads whose only "pain" was the
    # vertical's generic line, and the whole coupled pain->solution design collapsed to a
    # template. An agent whose reasoning step is disabled by default is not an agent.
    #
    # It costs money (OpenRouter, per lead). --no-llm is the escape hatch for a dry sweep
    # or a drained key; the run prints what it spent either way.
    ap.add_argument("--llm", action=argparse.BooleanOptionalAction, default=True,
                    help="review-pain extraction via LLM (COSTS MONEY). On by default; "
                         "use --no-llm to skip it and fall back to keyword pain hints.")
    ap.add_argument("--keep-portal-leads", action="store_true",
                    help="do NOT drop leads whose only web presence is a portal/social "
                         "listing (default is to drop them: a portal is not a prospect)")
    ap.add_argument("--crm-only", action="store_true",
                    help="skip enrichment (reviews/site/people) and only upsert what the "
                         "listing already knows. Fetches nothing and spends nothing — this "
                         "is the sweep that makes the local leads file redundant.")
    ap.add_argument("--skip-people", action="store_true",
                    help="skip the team/leadership crawl (a low-yield second pass on this "
                         "pool); halves per-lead crawl time. Emails still harvested.")
    ap.add_argument("--redo", action="store_true",
                    help="re-open every checkpointed lead, even fully enriched ones. "
                         "Normally a full run only re-opens leads whose checkpoint came "
                         "from a --crm-only sweep.")
    ap.add_argument("--dry-run", action="store_true",
                    help="do everything except write to the CRM")
    args = ap.parse_args()

    if args.verticals:
        bad = [v for v in args.verticals if v not in ACTIVE_VERTICALS]
        if bad:
            raise SystemExit(f"Not active verticals: {bad}. Active: {ACTIVE_VERTICALS}")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Top up the discovery pool with a gosom burst — ONLY when enrichment is running dry.

    python scripts/refill_pool.py                          # status only, never scrapes
    python scripts/refill_pool.py --min-pending 25         # same, with your threshold
    python scripts/refill_pool.py --min-pending 25 --max-new 30 --yes    # burst if low

## Why this exists

Scraping Maps and enriching a site cost wildly different wall-clock: a gosom burst is
minutes, enriching the batch it produces is hours (150 sites x ~12s/page). So the natural
rhythm is *scrape rarely, enrich constantly* — and the way to keep gosom's Google footprint
low, which is what lowers the odds of a datacenter-IP block, is to fire it only when the
pool of un-enriched leads is running out. A scraper that runs 24/7 is the profile Google
blocks; a short burst every few days, triggered by depletion, is not.

This is the LOW-WATER-MARK trigger. It reads how much enrichable work is left and does
nothing while there is plenty. Only when `pending < --min-pending` does it consider a burst,
and even then it prints the plan and STOPS unless `--yes` is given.

## The boundary this script must never cross

It grows the POOL FILE and nothing else. It does NOT enrich, does NOT write to the CRM, and
spends NO credits (gosom scraping is free). Enrichment stays a separate, operator- or
schedule-controlled `discover.py` run. Keeping the two apart is the safety property: a
refill that silently kept going into enrichment would be a bulk write to the shared
production CRM fired by a timer, which is exactly the kind of unattended spend the rules
forbid.

Fail closed: if gosom is missing, or a burst comes back EMPTY (the shape a datacenter-IP
block takes — gosom returns no rows rather than an error), that is reported loudly and the
pool is left untouched. An empty burst must never look like "the pool was topped up".
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import nav_env
import polite_fetch
import discover

ACTIVE_VERTICALS = discover.ACTIVE_VERTICALS
STATE_PATH = discover.STATE_PATH
DEFAULT_POOL = nav_env.env("NAVAIA_LEADS_FILE") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "leads_enriched_people.json")


def load_pool(path: str) -> list[dict]:
    """The candidate pool discover.py reads. A list, or {'leads': [...]}."""
    try:
        with io.open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    leads = data.get("leads", data) if isinstance(data, dict) else data
    return [l for l in leads if isinstance(l, dict)]


def save_pool(path: str, leads: list[dict]) -> None:
    """Atomic replace — a killed write must not truncate the pool. Same discipline as
    polite_fetch.save_store, which exists because a plain json.dump destroyed results twice
    on 2026-07-20."""
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def pending_count(pool: list[dict], done: dict) -> tuple[int, int]:
    """(pending, enriched) — how many pool leads still need a full enrichment pass.

    A lead counts as pending if it was never checkpointed OR its checkpoint came from a
    --crm-only sweep (`enriched` false). This is the SAME rule discover.needs_work uses, so
    the number here is exactly what a full discover run would pick up.
    """
    pending = enriched = 0
    for lead in pool:
        key = discover.lead_key(lead)
        entry = done.get(key)
        if entry is None or not entry.get("enriched", False):
            pending += 1
        else:
            enriched += 1
    return pending, enriched


def known_keys(pool: list[dict], done: dict) -> set[str]:
    """Every identity already in the pool or already processed — the dedup set for a burst.
    Deduping on `lead_key` (place_id, then phone, then name) is what stops a refill from
    piling the same company back in every few days."""
    keys = {discover.lead_key(l) for l in pool}
    keys |= set(done.keys())
    keys.discard("")
    return keys


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pool", default=os.path.abspath(DEFAULT_POOL),
                    help="the candidate file discover.py reads (also where new leads land)")
    ap.add_argument("--min-pending", type=int, default=25,
                    help="scrape only when fewer than this many leads still need enriching")
    ap.add_argument("--max-new", type=int, default=30,
                    help="cap NEW leads added per burst — the operator's batch size, so a "
                         "single query flood cannot dump hundreds into the pool")
    ap.add_argument("--verticals", default=",".join(ACTIVE_VERTICALS),
                    help="comma-separated; which verticals to scrape for")
    ap.add_argument("--depth", default=discover.GMAPS_DEPTH,
                    help="gosom scroll depth — keep LOW, footprint scales with it")
    ap.add_argument("--gmaps-binary",
                    default=nav_env.env("NAVAIA_GMAPS_BINARY") or "google-maps-scraper",
                    help="the gosom binary on PATH (baked into the cloud image)")
    ap.add_argument("--yes", action="store_true",
                    help="actually run the gosom burst; without it, status + plan only")
    args = ap.parse_args()

    verticals = [v.strip() for v in args.verticals.split(",") if v.strip()]
    bad = [v for v in verticals if v not in ACTIVE_VERTICALS]
    if bad:
        print(f"Refusing: {bad} are not active verticals {ACTIVE_VERTICALS}.")
        return 1

    pool = load_pool(args.pool)
    done = polite_fetch.load_store(STATE_PATH).get("done", {})
    pending, enriched = pending_count(pool, done)

    print(f"pool: {args.pool}")
    print(f"  {len(pool):>4} candidates   {enriched:>4} enriched   {pending:>4} still pending")
    print(f"  threshold --min-pending = {args.min_pending}\n")

    if pending >= args.min_pending:
        print(f"Pending ({pending}) is at or above the threshold ({args.min_pending}). "
              f"There is enough to enrich — NO scrape. This is the whole point of the "
              f"trigger: gosom fires only when the pool runs dry.")
        return 0

    print(f"Pending ({pending}) is BELOW the threshold — a refill burst is due.")
    if not args.yes:
        print(f"\nPLAN: run gosom for {verticals} at depth {args.depth}, append up to "
              f"{args.max_new} NEW leads (deduped) to the pool. Enriches nothing, writes no "
              f"CRM, spends no credits.\nNothing done. Re-run with --yes to fire the burst.")
        return 0

    # ── the burst ────────────────────────────────────────────────────────────────────
    out_dir = polite_fetch.state_dir()
    try:
        scraped = discover.source_gmaps(verticals, args.gmaps_binary, out_dir, args.depth)
    except SystemExit as e:
        # source_gmaps fails closed on a missing binary — surface it, change nothing.
        print(f"\nBURST ABORTED — {e}")
        return 1

    if not scraped:
        # The datacenter-IP block shape: gosom returns no rows, not an error. Never let an
        # empty burst read as a successful top-up. If this recurs, the cloud IP is the
        # problem — see scripts/gmaps_probe.py and switch the burst to a residential runner.
        print("\nBURST RETURNED ZERO LISTINGS. This is what a datacenter-IP block looks "
              "like (gosom yields nothing rather than erroring). Pool left UNCHANGED. Run "
              "scripts/gmaps_probe.py to confirm whether this IP is being served.")
        return 2

    seen = known_keys(pool, done)
    fresh = []
    for lead in scraped:
        key = discover.lead_key(lead)
        if not key or key in seen:
            continue
        seen.add(key)
        fresh.append(lead)
        if len(fresh) >= args.max_new:
            break

    print(f"\nscraped {len(scraped)} listings -> {len(fresh)} NEW after dedup "
          f"(capped at {args.max_new})")
    if not fresh:
        print("Every listing was already known. Pool left unchanged — nothing to add.")
        return 0

    save_pool(args.pool, pool + fresh)
    print(f"Appended {len(fresh)} new candidate(s) -> {args.pool}")
    print("They are UN-enriched. The next `discover.py` run (operator or scheduled) will "
          "enrich them. This script deliberately does not.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

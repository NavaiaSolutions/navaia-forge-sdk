#!/usr/bin/env python3
"""Paid fallback for company sizing: Snov.io domain-search, ~1 credit per domain.

Runs ONLY on leads the free website crawl (enrich_company_size.py) could not size, and
ONLY when the operator triggers it. Credits are budgeted per-item by the operator, so
this script prints the exact domain list and cost and requires --yes to spend.

WHY THE NAME GUARD EXISTS (measured 2026-07-20, before this script was trusted):
Snov keys on the domain STRING, not the business. Querying `efsim.sa` returned
`related_domains: [efsim.nl, efsim.com, efsim.ru]` and a size of "10001+" — the same band
as Saudi Aramco — while reporting 25 emails and 687 prospects. It had merged unrelated
companies that happen to share the token "efsim". Taking that at face value would have
ranked a Riyadh facilities firm on a foreign company's headcount.

So a result is only accepted as `found` when Snov's `company_name` plausibly matches the
lead we asked about. A mismatch is recorded as `snov_ambiguous` with both names kept, for
a human to settle. An implausible band (10001+ on a domain with almost no prospects) is
flagged `snov_suspect`. Neither is ever silently promoted to a headcount.

Verified good on the same run: `goamaken.com` -> "201-500", "Amaken International Group",
consistent with that company's own site claim of "over 50 certified professionals".

Coverage is partial — 2 of 5 Saudi SMB domains tested had any record at all. A domain with
no record costs a credit and yields nothing; that is expected, not a failure.

Usage:
    python scripts/enrich_company_size_snov.py --top 18            # show plan + cost, spend nothing
    python scripts/enrich_company_size_snov.py --top 18 --yes      # actually spend
    python scripts/enrich_company_size_snov.py --domains a.sa,b.sa --yes
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import httpx

import pipeline_prep as prep
import rank_priority_leads
from enrich_company_size import CACHE, load_cache, save_cache, ACTIVE_VERTICALS

SNOV = "https://api.snov.io/v2/domain-search"

# "51-200" / "201-500" / "10001+" / "1-10"  -> lower bound of the band.
_BAND = re.compile(r"^\s*([\d,]+)\s*(?:-|–|\+)")

# A 10001+ band on a domain with a handful of prospects is a merged/wrong profile, not a
# Saudi SMB with ten thousand staff. Treat as suspect rather than as a headcount.
_SUSPECT_BAND = "10001+"
_SUSPECT_MIN_PROSPECTS = 2000


def _token_set(name: str) -> set[str]:
    """Comparable word tokens: drop legal/descriptive noise that differs between sources."""
    noise = {"company", "co", "llc", "ltd", "limited", "group", "international", "est",
             "establishment", "for", "and", "the", "شركة", "مؤسسة", "مجموعة", "المحدودة",
             "الدولية", "العالمية", "و"}
    words = re.findall(r"[A-Za-z؀-ۿ]+", (name or "").lower())
    return {w for w in words if w not in noise and len(w) > 2}


def name_matches(lead_name: str, snov_name: str) -> bool:
    """True when Snov's company plausibly IS our lead. Conservative on purpose."""
    a, b = _token_set(lead_name), _token_set(snov_name)
    if not a or not b:
        return False
    # Any shared distinctive token is enough — the two sources name companies differently
    # (Arabic vs English, with/without legal form), but a real match shares a stem.
    return bool(a & b)


def band_floor(size: str) -> int | None:
    m = _BAND.match(size or "")
    return int(m.group(1).replace(",", "")) if m else None


def snov_company(domain: str, token: str) -> tuple[dict, dict]:
    """(data, meta) from Snov domain-search for one domain. Costs ~1 credit."""
    h = {"Authorization": "Bearer " + token}
    r = httpx.post(f"{SNOV}/start", headers=h, json={"domain": domain}, timeout=40)
    r.raise_for_status()
    task = r.json()["meta"]["task_hash"]
    for _ in range(20):
        time.sleep(4)
        d = httpx.get(f"{SNOV}/result/{task}", headers=h, timeout=40).json()
        status = (d.get("meta") or {}).get("status") or d.get("status")
        if status in ("completed", "finished", "error"):
            data = d.get("data")
            return (data if isinstance(data, dict) else {}), (d.get("meta") or {})
    return {}, {}


def resolve(lead_company: str, domain: str, token: str) -> dict:
    data, meta = snov_company(domain, token)
    out = {"employees": None, "source": "snov", "evidence": "", "status": "snov_no_record",
           "snov_name": "", "snov_size": ""}
    if not data:
        return out

    snov_name, size = data.get("company_name") or "", data.get("size") or ""
    out.update(snov_name=snov_name, snov_size=size)
    prospects = meta.get("prospects_count") or 0

    if not name_matches(lead_company, snov_name):
        out["status"] = "snov_ambiguous"
        out["evidence"] = f"Snov returned '{snov_name}' for {domain} — does not match '{lead_company}'"
        return out
    if size == _SUSPECT_BAND and prospects < _SUSPECT_MIN_PROSPECTS:
        out["status"] = "snov_suspect"
        out["evidence"] = f"band {size} but only {prospects} prospects — likely a merged profile"
        return out

    floor = band_floor(size)
    if floor is None:
        out["status"] = "snov_no_size"
        return out
    out.update(employees=floor, status="found",
               evidence=f"Snov size band '{size}' for {snov_name} ({domain}); "
                        f"{prospects} prospects")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verticals", default=",".join(ACTIVE_VERTICALS))
    ap.add_argument("--top", type=int, default=0, help="consider the top N ranked leads")
    ap.add_argument("--domains", default="", help="explicit comma-separated domains")
    ap.add_argument("--yes", action="store_true", help="actually spend credits")
    args = ap.parse_args()

    verticals = [v.strip() for v in args.verticals.split(",") if v.strip()]
    cache = load_cache()

    leads = rank_priority_leads.rank(verticals)
    if args.top:
        leads = leads[: args.top]
    if args.domains:
        want = {d.strip().lower() for d in args.domains.split(",") if d.strip()}
        leads = [l for l in leads
                 if urlparse(l.get("website") or "").netloc.lower().replace("www.", "") in want]

    # Only leads the free crawl failed to size, that have a domain to query.
    # Deduplicated by domain: sibling records (branches, or a training arm and its parent)
    # share one website, and Snov bills per domain — querying it twice buys nothing.
    todo, seen_hosts = [], set()
    for l in leads:
        host = urlparse(l.get("website") or "").netloc.lower().replace("www.", "")
        v = cache.get(l["person_id"]) or {}
        if host and not v.get("employees") and host not in seen_hosts:
            seen_hosts.add(host)
            todo.append((l, host))

    if not todo:
        print("Nothing to resolve — every ranked lead is either sized or has no domain.")
        return

    print(f"SNOV PLAN — {len(todo)} domain(s), ~{len(todo)} credit(s):\n")
    for l, host in todo:
        print(f"  {l['company'][:42]:42} {host}")
    if not args.yes:
        print(f"\nNothing spent. Re-run with --yes to spend ~{len(todo)} credits.")
        return

    token = prep._snov_token()
    for i, (l, host) in enumerate(todo, 1):
        res = resolve(l["company"], host, token)
        entry = {**(cache.get(l["person_id"]) or {}),
                 "company": l["company"], "sector": l["sector"],
                 "website": l.get("website") or "", **res}
        cache[l["person_id"]] = entry
        save_cache(cache)
        shown = f"{res['employees']}+ ({res['snov_size']})" if res["employees"] else res["status"]
        print(f"  [{i}/{len(todo)}] {l['company'][:40]:40} -> {shown}")
        if res["evidence"] and not res["employees"]:
            print(f"        {res['evidence']}")

    big = [v for v in cache.values() if (v.get("employees") or 0) >= 50]
    print(f"\n{len(big)} lead(s) now confirmed at 50+ employees:")
    for v in sorted(big, key=lambda x: -x["employees"]):
        print(f"  {v['employees']:>6}  {v['company'][:44]:44} via {v.get('source')}")
    print(f"\nCache: {CACHE}")


if __name__ == "__main__":
    main()

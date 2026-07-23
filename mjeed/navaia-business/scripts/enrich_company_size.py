#!/usr/bin/env python3
"""Establish company headcount for the priority ranking, from the company's own pages.

Why this exists: the "50+ employees = high priority" rule (operator decision 2026-07-20)
has NO data source in the pipeline — Twenty's `employees` field is empty on every one of
Mjeed's companies and no LinkedIn URLs are stored. This script produces that missing
signal the only honest way available: it reads what the company says about itself.

Two passes per lead, both through the operator's own scraping skill
(agent_scraping_skill -> micro_scraper -> crawl4ai), so whatever works here works
identically when Rashid runs it in the cloud runtime:

  1. SITE  — homepage + about/team paths. Extracts an explicit headcount claim
             ("أكثر من ٢٠٠ موظف", "team of 120", "نضم 85 موظفًا") and, critically,
             harvests any LinkedIn company URL out of the footer. That footer link is
             how we get a LinkedIn address at all, since none are stored in the CRM.
LinkedIn is deliberately NOT crawled (researched 2026-07-20). Scraping it violates the
User Agreement regardless of tooling, 2026 enforcement is fingerprint- and IP-based, and
LinkedIn sued Proxycurl out of business in 2025 for exactly this. Any LinkedIn URL found
in a footer is RECORDED for a human to open manually — never fetched by this script.

Government sources were also evaluated and rejected for prospecting: Wathq API 18 does
serve GOSI employment data (GOSI's own bands: 1-5 small, 6-49 micro, 50-249 medium,
250+ large — so "50+" means "medium or larger"), but it is consent-gated to the
establishment itself and is personal data under PDPL. It is a lawful way to check your
OWN headcount, not a prospect's.

A lead whose headcount cannot be established is written as employees=None with
status="unknown". It is NOT assumed small and NOT assumed large — the ranker treats
unknown as its own tier. Never edit this file to estimate headcount from review counts
or company-name grandeur: an invented size signal silently reorders the send list, which
is the same failure class as the 2026-07-19 fabricated-lead incident.

Results are cached in company_size.json and the run is resumable — reruns only crawl
leads with no cached verdict, so an interrupted batch costs nothing to restart.

Usage:
    python scripts/enrich_company_size.py --limit 10       # crawl 10 uncached leads
    python scripts/enrich_company_size.py                  # crawl every uncached lead
    python scripts/enrich_company_size.py --recheck        # ignore the cache
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pipeline_prep as prep
import site_facts
from agent_scraping_skill import agent_scraping_skill
from micro_scraper import USER_AGENT

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "company_size.json")
ACTIVE_VERTICALS = ["Real Estate", "Contracting & Facilities", "Training Institutes"]

# Pages that carry a headcount claim when one exists at all. Arabic slugs included —
# Saudi SMB sites put the company story on "من-نحن" far more often than on /about.
# Kept SHORT on purpose: every extra path costs a full crawl-delay against the same host,
# and a company that states its size states it on the homepage or the about page.
SIZE_PATHS = ["", "about", "about-us", "من-نحن"]

_LINKEDIN = re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/company/[A-Za-z0-9\-_%]+", re.I)

# Arabic-Indic digits -> ASCII, so "٢٠٠ موظف" is matched by the same numeric patterns.
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

# Explicit headcount claims. Each pattern's group(1) is the number of PEOPLE.
_SITE_PATTERNS = [
    re.compile(r"(?:أكثر من|اكثر من|يزيد على|ما يزيد عن|يفوق)\s*(\d{2,5})\s*(?:موظف|موظفًا|موظفا|عامل|فني|مهندس|عضو)"),
    re.compile(r"(?:يضم|تضم|نضم|لدينا|يعمل لدينا|فريق (?:من|يضم))\s*(?:أكثر من\s*)?(\d{2,5})\s*(?:موظف|موظفًا|موظفا|عامل|فني|مهندس|عضو)"),
    re.compile(r"(\d{2,5})\s*\+?\s*(?:موظف|موظفًا|موظفا|عامل|فني|مهندس)"),
    re.compile(r"(?:team of|staff of|workforce of|more than|over)\s*(\d{2,5})\s*(?:employees|staff|people|engineers|technicians)?", re.I),
    re.compile(r"(\d{2,5})\s*\+?\s*(?:employees|staff members|professionals|engineers)", re.I),
]

# LinkedIn's employee band, e.g. "51-200 employees" / "1,001-5,000 employees" / "10K+".
_LI_BAND = re.compile(r"([\d,]{1,7})\s*(?:-|–|to)\s*([\d,]{1,7})\s*employees", re.I)
_LI_PLUS = re.compile(r"([\d,]{1,7})\s*\+\s*employees", re.I)


def _norm(text: str) -> str:
    return (text or "").translate(_AR_DIGITS)


def _num(s: str) -> int:
    return int(s.replace(",", ""))


# --- Politeness layer -------------------------------------------------------------
# Moved to polite_fetch.py so every crawler in the repo shares one implementation. Keeping
# it here meant enrich_emails_crawl4ai.py crawled with no robots check and no delay at all.
# Re-exported under the old private names so existing callers and tests keep working.
from polite_fetch import (  # noqa: E402
    DEFAULT_DELAY, allowed as _allowed, fetch as _scrape, robots as _robots,
    save_store, throttle as _throttle,
)


def _headcount_from_site(markdown: str) -> tuple[int | None, str]:
    """Largest credible explicit headcount claim on the page, with the sentence as evidence."""
    best, evidence = None, ""
    for pat in _SITE_PATTERNS:
        for m in pat.finditer(markdown):
            n = _num(m.group(1))
            # Above ~50k it is a revenue/area/project figure that caught the pattern, not people.
            if not 5 <= n <= 50000:
                continue
            if best is None or n > best:
                best = n
                start, end = max(0, m.start() - 60), min(len(markdown), m.end() + 60)
                evidence = " ".join(markdown[start:end].split())
    return best, evidence


def _headcount_from_linkedin(markdown: str) -> tuple[int | None, str]:
    """Lower bound of LinkedIn's employee band (a '51-200' company is '50+' for our rule)."""
    m = _LI_BAND.search(markdown)
    if m:
        return _num(m.group(1)), " ".join(m.group(0).split())
    m = _LI_PLUS.search(markdown)
    if m:
        return _num(m.group(1)), " ".join(m.group(0).split())
    return None, ""


def enrich_one(lead: dict) -> dict:
    """Crawl one lead's site (then its LinkedIn) and return a size verdict."""
    site = (lead.get("website") or "").strip()
    verdict = {"company": lead["company"], "sector": lead["sector"], "website": site,
               "employees": None, "source": None, "evidence": "", "linkedin": "",
               "status": "unknown"}
    if not site:
        verdict["status"] = "no_website"
        return verdict

    root = site if site.startswith("http") else "https://" + site
    base = f"{urlparse(root).scheme}://{urlparse(root).netloc}/"

    pages, linkedin = [], ""
    for path in SIZE_PATHS:
        md = _scrape(urljoin(base, path) if path else root)
        if not md:
            continue
        pages.append(md)
        if not linkedin:
            m = _LINKEDIN.search(md)
            if m:
                linkedin = m.group(0)
        # Stop only when this crawl has produced BOTH things it is here for: the headcount
        # AND at least one publishable fact for the outreach opener. Breaking on headcount
        # alone used to skip the about/من-نحن pages, which is exactly where a company states
        # its coverage and scale — goamaken.com's homepage is a portal, and its "13 regions"
        # line lives one page deeper.
        if _headcount_from_site(md)[0] is not None and site_facts.extract("\n".join(pages)):
            break
    if not pages:
        verdict["status"] = "site_unreachable"
        return verdict

    # The LinkedIn URL is RECORDED for a human to open, never crawled — see the module
    # docstring. Harvesting it from the footer still has value: it is the fastest manual
    # confirmation path when the site itself says nothing about headcount.
    verdict["linkedin"] = linkedin
    # How many of the attempted paths actually returned a page. Without this, "unknown"
    # conflates "we read the site and it states no headcount" with "only one page of four
    # loaded" — a materially weaker conclusion. Record it so the verdict can be judged.
    verdict["pages_fetched"] = len(pages)
    # Facts the company published about ITSELF — coverage, branches, projects, tenure.
    # Feeds the outreach opener, which is otherwise a generic per-vertical sentence. Free:
    # these pages are already fetched for the headcount, and were previously discarded.
    verdict["site_facts"] = site_facts.extract("\n".join(pages))
    n, ev = _headcount_from_site("\n".join(pages))
    if n is not None:
        verdict.update(employees=n, source="website", evidence=ev, status="found")
    return verdict


def load_cache() -> dict:
    try:
        with io.open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cache(cache: dict) -> None:
    """Merge into whatever is on disk, then write atomically.

    Delegates to polite_fetch.save_store — the one implementation of read-merge-atomic-write
    in the repo — so this cache and the shared page/state store cannot drift apart. The
    behaviour is unchanged and still matters: a plain dump is a lost-update bug when two
    sizing runs overlap (crawl + Snov, or two crawls). That happened on 2026-07-20, when a
    long crawl holding a stale snapshot erased 16 credits' worth of Snov verdicts one save at
    a time. save_store re-reads before every write so a concurrent writer's entries survive,
    and os.replace never leaves a half-written file if we are killed mid-dump.

    A later verdict for the SAME lead still wins — that is a deliberate refresh, not a
    clash. Only entries this process never touched are preserved from disk.
    """
    save_store(CACHE, cache)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verticals", default=",".join(ACTIVE_VERTICALS))
    ap.add_argument("--only", default="",
                    help="comma-separated company-name substrings — crawl only these")
    ap.add_argument("--top", type=int, default=0,
                    help="crawl the top N leads from rank_priority_leads, in priority order")
    ap.add_argument("--limit", type=int, default=0, help="crawl at most N uncached leads")
    ap.add_argument("--recheck", action="store_true", help="ignore cached verdicts")
    args = ap.parse_args()

    verticals = [v.strip() for v in args.verticals.split(",") if v.strip()]
    if args.top:
        # Crawl in priority order, so an interrupted run has still sized the best leads.
        import rank_priority_leads
        leads = rank_priority_leads.rank(verticals)[: args.top]
    else:
        leads = prep.not_contacted_leads(verticals)
    if args.only:
        # An explicit --only names a company the operator wants sized NOW, so search every
        # one of Mjeed's leads rather than only the Not Contacted ones. Restricting it to
        # the outreach queue made "--only <already contacted company>" match nothing, which
        # is never what someone naming a company means.
        picks = [p.strip() for p in args.only.split(",") if p.strip()]
        everyone = []
        for p in prep._crm_people():
            company = (p.get("company") or {}).get("name") or ""
            if any(pick in company for pick in picks):
                everyone.append({
                    "person_id": p["id"], "company": company,
                    "sector": p.get("sector") or "",
                    "website": ((p.get("company") or {}).get("domainName") or {}).get("primaryLinkUrl") or "",
                })
        leads = everyone
        print(f"--only matched {len(leads)} lead(s) across all lead statuses")
    cache = {} if args.recheck else load_cache()

    todo = [l for l in leads if l["person_id"] not in cache]
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(leads)} lead(s) in scope | {len(cache)} cached | crawling {len(todo)}")

    for i, lead in enumerate(todo, 1):
        v = enrich_one(lead)
        prior = cache.get(lead["person_id"]) or {}
        # A crawl that finds no headcount must NOT erase one we already established from
        # another source. Re-crawling three leads for their site_facts silently wiped
        # Snov-derived sizes on 2026-07-20 and dropped them out of the 50+ set. Absence of
        # evidence in this pass is not evidence of absence: keep the known value, keep the
        # source that earned it, and let the new pass contribute what it actually found.
        if not v.get("employees") and prior.get("employees"):
            v["employees"] = prior["employees"]
            v["source"] = prior.get("source")
            v["evidence"] = prior.get("evidence", "")
            v["snov_size"] = prior.get("snov_size", "")
            v["status"] = "found"
        cache[lead["person_id"]] = v
        save_cache(cache)  # after every lead: a killed run keeps everything it earned
        size = f"{v['employees']} ({v['source']})" if v["employees"] else v["status"]
        print(f"  [{i}/{len(todo)}] {v['company'][:44]:44} -> {size}")

    scope = {l["person_id"]: l for l in leads}
    results = [v for pid, v in cache.items() if pid in scope]
    found = [v for v in results if v["employees"]]
    big = [v for v in found if v["employees"] >= 50]
    print(f"\n{len(found)} of {len(results)} resolved by crawl | {len(big)} at 50+ employees")
    for v in sorted(big, key=lambda x: -x["employees"]):
        print(f"  50+  {v['company'][:44]:44} {v['employees']:>6} via {v['source']}")

    # The paid fallback, as a PROPOSAL only. The crawl is free and answers many leads;
    # Snov costs credits, so this script never calls it — it hands you the exact list and
    # the exact cost, and you decide. Nothing here spends anything.
    unresolved = [(pid, v) for pid, v in cache.items()
                  if pid in scope and not v["employees"] and v["status"] != "no_website"]
    if not unresolved:
        print("\nNothing unresolved — no Snov spend needed.")
    else:
        print(f"\n--- SNOV CANDIDATES ({len(unresolved)}) — the crawl could not size these ---")
        print("Ranked by priority. ~1 credit per domain. Nothing spent yet.\n")
        order = {l["person_id"]: i for i, l in enumerate(leads)}
        for pid, v in sorted(unresolved, key=lambda kv: order.get(kv[0], 999)):
            host = urlparse(v["website"] or "").netloc.replace("www.", "") or "(no domain)"
            li = "  linkedin:" + v["linkedin"] if v["linkedin"] else ""
            print(f"  {v['company'][:40]:40} {host:28} [{v['status']}]{li}")
        print(f"\nTo spend: python scripts/enrich_company_size_snov.py --domains "
              f"{','.join(urlparse(v['website']).netloc.replace('www.','') for _, v in unresolved if v['website'])}")
    print(f"\nCache: {CACHE}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Email enrichment through the Crawl4AI micro-scraper (browser-rendered).

Why this exists alongside enrich_emails.py: the plain-HTTP crawler gets 403'd by a large
share of Saudi SMB sites (measured 2026-07-19 — 14 of 16 sites yielded nothing, and
themiran.net returns 403 to urllib but renders fine in a browser). crawl4ai drives a real
browser, so it gets the page the operator would see. This is the difference between a lead
being email-reachable or WhatsApp-only.

Runs the operator's own scraping skill (scripts/agent_scraping_skill.py -> micro_scraper.py),
so whatever works here works identically when Rashid runs it in the cloud runtime.

Usage:
    python scripts/enrich_emails_crawl4ai.py --dry-run     # find emails, write nothing
    python scripts/enrich_emails_crawl4ai.py               # find + PATCH the CRM
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
import time
from urllib.parse import urljoin, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import httpx

import nav_env
import pipeline_prep as prep
import polite_fetch
from agent_scraping_skill import agent_scraping_skill

CRM = nav_env.crm_base()
ACTIVE = ["Real Estate", "Contracting & Facilities", "Training Institutes"]

# Pages worth a second look when the homepage has no address. Arabic slugs included —
# Saudi sites very often put the mailbox only on the "اتصل بنا" page.
CONTACT_PATHS = ["", "contact", "contact-us", "contactus", "about", "about-us",
                 "ar/contact", "اتصل-بنا", "تواصل-معنا", "من-نحن"]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Addresses that are never the business's own mailbox.
JUNK = re.compile(r"(sentry|wixpress|example\.|godaddy|cloudflare|jquery|\.png$|\.jpg$|"
                  r"\.webp$|@2x|sentry\.io|no-?reply|domain\.com|yourdomain|email\.com)", re.I)
PREFERRED = ["info@", "contact@", "sales@", "admin@", "support@", "office@"]


def harvest(markdown: str, domain: str, site: str = "") -> list[str]:
    found = []
    for e in EMAIL_RE.findall(markdown or ""):
        e = e.strip().lower().rstrip(".")
        if JUNK.search(e) or e in found:
            continue
        # A mailbox on a third-party host is that host's, not the lead's. The
        # same-domain sort below would otherwise RANK IT FIRST when the page we
        # crawled IS the third party — how a property portal's own info@ mailbox got
        # sent a lead's outreach on 2026-07-21.
        if not prep.email_belongs_to(e, site or f"https://{domain}"):
            continue
        found.append(e)
    # Same-domain addresses first — a lead's own mailbox beats a webmaster's gmail.
    root = domain.replace("www.", "")
    found.sort(key=lambda e: (root not in e.split("@")[-1], PREFERRED.index(
        next((p for p in PREFERRED if e.startswith(p)), PREFERRED[-1]))))
    return found


def best_email(site: str, budget_pages: int = 4) -> tuple[str, list[str], list[str]]:
    """Crawl a few pages of one site; return (chosen, all_found, pages_tried)."""
    if not site.startswith("http"):
        site = "https://" + site
    domain = urlparse(site).netloc or site
    # No point crawling somebody else's portal for the lead's mailbox — it isn't there,
    # and anything found belongs to the portal. Treat it as "no website", which it is.
    if not prep.is_own_domain(site):
        return "", [], []
    all_found: list[str] = []
    tried: list[str] = []
    for path in CONTACT_PATHS[:budget_pages]:
        url = urljoin(site.rstrip("/") + "/", path) if path else site
        tried.append(path or "/")
        # Through polite_fetch, NOT agent_scraping_skill directly. This function used to
        # call the scraper with no robots.txt check and no rate limiting at all, so it
        # crawled every site flat out (found 2026-07-20). fetch() returns '' for a
        # disallowed or dead page, which this loop already treats as "nothing here".
        markdown = polite_fetch.fetch(url)
        if not markdown:
            continue
        for e in harvest(markdown, domain, site):
            if e not in all_found:
                all_found.append(e)
        if all_found:                     # stop as soon as we have something real
            break
    return (all_found[0] if all_found else ""), all_found, tried


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    targets = []
    for p in prep._crm_people():
        if p.get("sector") not in ACTIVE:
            continue
        if (p.get("emails") or {}).get("primaryEmail"):
            continue
        web = ((p.get("company") or {}).get("domainName") or {}).get("primaryLinkUrl") or ""
        if web:
            targets.append((p["id"], (p.get("name") or {}).get("firstName", ""), web))

    print(f"{len(targets)} lead(s) without an email but with a website\n")
    hdr = {"Authorization": "Bearer " + nav_env.env("TWENTY_TOKEN"),
           "Content-Type": "application/json"}
    hits = 0
    for pid, name, web in targets[:args.limit]:
        t0 = time.time()
        chosen, found, tried = best_email(web)
        secs = time.time() - t0
        if chosen:
            hits += 1
            print(f"  FOUND {name[:30]:30} {chosen:34} ({secs:.0f}s, pages={len(tried)})")
            if found[1:]:
                print(f"        also: {', '.join(found[1:4])}")
            if not args.dry_run:
                r = httpx.patch(f"{CRM}/rest/people/{pid}", headers=hdr,
                                json={"emails": {"primaryEmail": chosen}}, timeout=30)
                print(f"        CRM {'OK' if r.status_code < 300 else 'ERR ' + str(r.status_code)}")
        else:
            print(f"  none  {name[:30]:30} {web[:34]:34} ({secs:.0f}s, pages={len(tried)})")
    print(f"\n{hits}/{len(targets[:args.limit])} enriched"
          f"{' (dry run — CRM untouched)' if args.dry_run else ''}")


if __name__ == "__main__":
    main()

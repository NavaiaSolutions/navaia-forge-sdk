#!/usr/bin/env python3
"""Reveal email addresses for shortlisted decision-makers found by fetch_prospects.py.

Separate from fetch_prospects.py on purpose: finding a prospect costs ~1 credit per DOMAIN
and is cheap enough to run broadly, while revealing an address is billed per PERSON. So the
find is wide and the reveal is narrow — only people actually worth a first touch.

Nothing here writes to the CRM and nobody is contacted. Output is a reviewed contact list.

THE SHORTLIST
Ranked by how directly the role owns the pain NAVAIA sells against:
  1 owner/CEO/deputy         decides alone at SMB scale
  2 customer service / ops   lives the missed-call, slow-reply problem daily
  3 procurement / branch     buys services, owns a P&L
  4 marketing                owns lead response, but often not the economic buyer
A company's BEST available contact is kept even at tier 4 — a named marketing manager
still beats info@, and for some leads it is the only name that exists. Tiers below the
cut (coordinators, warehouse, sales reps selling TO us) are dropped: they cannot buy and
burn the first touch.

Usage:
    python scripts/reveal_prospect_emails.py                 # show plan + cost
    python scripts/reveal_prospect_emails.py --yes           # spend credits
    python scripts/reveal_prospect_emails.py --per-company 2 --yes
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import httpx

import pipeline_prep as prep

IN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prospects.json")
OUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "contacts.json")

TIERS = [
    (1, re.compile(r"(owner|founder|chairman|\bceo\b|chief executive|deputy ceo|"
                   r"managing director|partner|general manager)", re.I)),
    (2, re.compile(r"(customer|client|service[s]? manager|operation|facilit)", re.I)),
    (3, re.compile(r"(procurement|purchas|contract|branch|commercial|business development)", re.I)),
    (4, re.compile(r"(marketing|revenue|sales manager)", re.I)),
]
# Cannot buy this product, whatever the title says.
_EXCLUDE = re.compile(r"(coordinator|warehouse|storekeeper|driver|technician|"
                      r"sales development|sales executive|intern|assistant)", re.I)


def tier(position: str) -> int:
    if _EXCLUDE.search(position or ""):
        return 99
    for rank, pat in TIERS:
        if pat.search(position or ""):
            return rank
    return 90


def shortlist(rows: list[dict], per_company: int) -> tuple[list[dict], list[dict]]:
    """Best `per_company` contacts per company, plus everyone dropped (for review)."""
    by_company: dict[str, list[dict]] = {}
    for r in rows:
        r = {**r, "tier": tier(r.get("position", ""))}
        by_company.setdefault(r["company"], []).append(r)

    keep, drop = [], []
    for company, people in by_company.items():
        people.sort(key=lambda p: p["tier"])
        usable = [p for p in people if p["tier"] < 90]
        keep += usable[:per_company]
        drop += usable[per_company:] + [p for p in people if p["tier"] >= 90]
    keep.sort(key=lambda p: (p["tier"], p["company"]))
    return keep, drop


def reveal(url: str, token: str) -> list[str]:
    """Start + poll one prospect's email search. Costs credits."""
    h = {"Authorization": "Bearer " + token}
    r = httpx.post(url, headers=h, timeout=40)
    if r.status_code >= 300:
        return []
    body = r.json()
    task = (body.get("meta") or {}).get("task_hash")
    result_url = (body.get("links") or {}).get("result")
    if not result_url and task:
        result_url = f"https://api.snov.io/v2/domain-search/prospects/search-emails/result/{task}"
    if not result_url:
        return []
    for _ in range(20):
        time.sleep(4)
        d = httpx.get(result_url, headers=h, timeout=40).json()
        status = (d.get("meta") or {}).get("status") or d.get("status")
        if status in ("completed", "finished", "error"):
            data = d.get("data") or {}
            emails = data.get("emails") if isinstance(data, dict) else data
            out = []
            for e in (emails or []):
                addr = e.get("email") if isinstance(e, dict) else e
                if addr:
                    out.append(addr)
            return out
    return []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-company", type=int, default=2)
    ap.add_argument("--yes", action="store_true", help="spend credits (billed per person)")
    args = ap.parse_args()

    with io.open(IN_FILE, encoding="utf-8") as f:
        rows = json.load(f)
    keep, drop = shortlist(rows, args.per_company)

    print(f"SHORTLIST — {len(keep)} person(s), billed per reveal:\n")
    for p in keep:
        print(f"  T{p['tier']}  {p['company'][:30]:30} {p['name'][:26]:26} {p['position'][:40]}")
    print(f"\nDROPPED ({len(drop)}) — cannot buy, or below the per-company cut:")
    for p in drop:
        print(f"  T{p['tier']:<2} {p['company'][:30]:30} {p['name'][:24]:24} {p['position'][:36]}")

    if not args.yes:
        print(f"\nNothing spent. Re-run with --yes to reveal {len(keep)} address(es).")
        return

    token = prep._snov_token()
    found = []
    for i, p in enumerate(keep, 1):
        if not p.get("email_lookup"):
            print(f"  [{i}/{len(keep)}] {p['name'][:28]:28} no lookup url")
            continue
        emails = reveal(p["email_lookup"], token)
        p["emails"] = emails
        if emails:
            found.append(p)
        print(f"  [{i}/{len(keep)}] {p['name'][:28]:28} -> {emails[0] if emails else 'not found'}")

    with io.open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(found, f, ensure_ascii=False, indent=1)
    print(f"\n{len(found)}/{len(keep)} resolved -> {OUT_FILE}")
    print("No CRM writes, nobody contacted. Review before importing.")


if __name__ == "__main__":
    main()

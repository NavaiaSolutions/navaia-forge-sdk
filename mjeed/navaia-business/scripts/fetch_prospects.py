#!/usr/bin/env python3
"""Find NAMED decision-makers at confirmed 50+ companies, via Snov domain prospects.

Why this exists: every lead contacted on 2026-07-20 was a generic `info@` inbox with the
company name duplicated into the Person record. Zero named contacts, so nobody earned the
scoring model's +10 for a named decision-maker, and every message opened with the
collective «القائمون على … الكرام» instead of a person's name. We optimised hard for
company SIZE while scoring zero on reaching the person who actually buys.

Cost: ~1 credit per domain for ~20 prospects (measured 2026-07-20). The search is cheap;
revealing an email costs extra and is NOT done here — this script only builds the
shortlist for a human to approve. Nothing is written to the CRM and nobody is emailed.

THE EMPLOYER GUARD
Snov keys prospects on the domain string, not the business. `efsim.sa` returns prospects
merged from efsim.nl/.com/.ru — including "Furqan Saeed, Facilities Manager Hitachi Energy
KSA", who does not work at our lead. This is the same contamination that gave efsim.sa a
size band of "10001+" (Aramco's band) on a Riyadh SMB. So a prospect whose stated position
names a DIFFERENT employer is dropped, and the drop is reported rather than hidden.

Usage:
    python scripts/fetch_prospects.py                 # all confirmed 50+ leads
    python scripts/fetch_prospects.py --min-employees 50 --json prospects.json
    python scripts/fetch_prospects.py --all-roles     # skip the buying-role filter
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
from enrich_company_size import load_cache

SNOV = "https://api.snov.io/v2/domain-search/prospects"

# Who actually buys a NAVAIA digital team: the person who owns the missed-call, slow-reply,
# uncollected-payment pain. Operations and the GM/owner line, plus procurement for the
# contracting vertical. Deliberately EXCLUDES IT and HR — they are not the economic buyer
# for reception/collections/sales automation, and targeting them wastes the first touch.
_BUYING_ROLES = re.compile(
    r"(chief|ceo|coo|cfo|founder|owner|partner|managing director|general manager|"
    r"vice president|\bvp\b|head of|director|manager)", re.I)
_ROLE_AREA = re.compile(
    r"(operation|business development|commercial|sales|procurement|purchas|customer|"
    r"client|facilit|collection|credit|marketing|revenue|branch|admin)", re.I)
# Never the buyer for this offer, even when the title is senior.
_WRONG_AREA = re.compile(
    r"(software|developer|engineer(?!ing manager)|\bit\b|information technology|security|"
    r"hse|safety|hr\b|human resource|recruit|talent|payroll|legal|counsel|"
    r"accountant|auditor|quality|training|teacher|instructor|nurse|doctor)", re.I)


def _tokens(text: str) -> set[str]:
    noise = {"company", "co", "ltd", "llc", "limited", "group", "international", "est",
             "the", "and", "for", "services", "service", "saudi", "arabia", "ksa"}
    return {w for w in re.findall(r"[a-z]+", (text or "").lower())
            if w not in noise and len(w) > 3}


def employer_conflict(position: str, company: str) -> str:
    """Return the conflicting employer if the title names a DIFFERENT one, else ''.

    Titles like "Facilities Manager Hitachi Energy KSA" carry the real employer. If that
    employer shares no distinctive token with our lead, this prospect belongs to a company
    Snov merged into the domain, not to us.
    """
    # Only titles with a trailing proper-noun run are worth testing; "Operations Manager"
    # names no employer at all and must not be treated as a conflict.
    m = re.search(r"\b(?:at|@|-|–|\|)\s*([A-Z][\w&.\- ]{3,40})$", position or "")
    if not m:
        m = re.search(r"(?:Manager|Director|Head|Officer|Executive|Supervisor)\s+"
                      r"([A-Z][\w&.\- ]{4,40})$", position or "")
    if not m:
        return ""
    claimed = m.group(1).strip()
    if _tokens(claimed) & _tokens(company):
        return ""  # same business, differently written
    return claimed


def is_buying_role(position: str) -> bool:
    p = position or ""
    if _WRONG_AREA.search(p):
        return False
    if not _BUYING_ROLES.search(p):
        return False
    # A bare "Chief/Founder/Owner/GM" needs no area — they own everything.
    if re.search(r"(chief exec|ceo|coo|founder|owner|managing director|general manager|"
                 r"partner)", p, re.I):
        return True
    return bool(_ROLE_AREA.search(p))


def prospects_for(domain: str, token: str) -> list[dict]:
    """One page (~20) of prospects for a domain. Costs ~1 credit."""
    h = {"Authorization": "Bearer " + token}
    r = httpx.post(f"{SNOV}/start", headers=h, json={"domain": domain}, timeout=40)
    if r.status_code >= 300:
        return []
    task = (r.json().get("meta") or {}).get("task_hash")
    if not task:
        return []
    for _ in range(25):
        time.sleep(4)
        d = httpx.get(f"{SNOV}/result/{task}", headers=h, timeout=40).json()
        status = (d.get("meta") or {}).get("status") or d.get("status")
        if status in ("completed", "finished", "error"):
            data = d.get("data")
            return data if isinstance(data, list) else []
    return []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-employees", type=int, default=50)
    ap.add_argument("--all-roles", action="store_true", help="skip the buying-role filter")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--yes", action="store_true", help="spend credits (~1 per domain)")
    args = ap.parse_args()

    sizes = load_cache()
    leads = [l for l in rank_priority_leads.rank()
             if (sizes.get(l["person_id"], {}).get("employees") or 0) >= args.min_employees]
    # Also include already-contacted leads, which rank() drops (it returns Not Contacted only).
    by_company = {l["company"]: l for l in leads}
    for pid, v in sizes.items():
        if (v.get("employees") or 0) >= args.min_employees and v["company"] not in by_company:
            by_company[v["company"]] = {"person_id": pid, "company": v["company"],
                                        "sector": v.get("sector", ""),
                                        "website": v.get("website", "")}

    todo = [(c, urlparse(l.get("website") or "").netloc.lower().replace("www.", ""))
            for c, l in by_company.items() if l.get("website")]
    if not todo:
        print("No sized leads with a domain.")
        return

    print(f"PLAN — {len(todo)} domain(s), ~{len(todo)} credit(s):")
    for c, d in todo:
        print(f"  {c[:42]:42} {d}")
    if not args.yes:
        print(f"\nNothing spent. Re-run with --yes to spend ~{len(todo)} credits.")
        return

    token = prep._snov_token()
    out, dropped_role, dropped_employer = [], 0, 0
    for i, (company, domain) in enumerate(todo, 1):
        rows = prospects_for(domain, token)
        kept = []
        for p in rows:
            name = " ".join(x for x in [p.get("first_name"), p.get("last_name")] if x).strip()
            position = (p.get("position") or "").strip()
            conflict = employer_conflict(position, company)
            if conflict:
                dropped_employer += 1
                continue
            if not args.all_roles and not is_buying_role(position):
                dropped_role += 1
                continue
            kept.append({"company": company, "domain": domain, "name": name,
                         "position": position, "linkedin": p.get("source_page") or "",
                         "email_lookup": p.get("search_emails_start") or ""})
        out += kept
        print(f"  [{i}/{len(todo)}] {company[:38]:38} {len(rows):3} found -> {len(kept)} buying-role")

    print(f"\n{len(out)} decision-maker(s) across {len(todo)} companies")
    print(f"  dropped: {dropped_role} wrong role, {dropped_employer} different employer\n")
    for r in out:
        print(f"  {r['company'][:30]:30} {r['name'][:26]:26} {r['position'][:44]}")

    if args.json_out:
        with io.open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(f"\nWrote {len(out)} -> {args.json_out}")
    print("\nNo emails revealed, no CRM writes, nobody contacted. Review before the next step.")


if __name__ == "__main__":
    main()

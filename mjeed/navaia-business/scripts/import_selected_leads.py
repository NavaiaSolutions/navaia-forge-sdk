#!/usr/bin/env python3
"""Import the merged/selected scrape pool into Twenty CRM as Not Contacted leads.

This is the LOCAL, deterministic stand-in for Nora's CRM-import step (script-authority
doctrine, workforce/POSTMORTEM_2026-07-14.md): the same field mapping and CRM quirks,
run by a script rather than an LLM so the write is exact and auditable.

Reads selected_leads.json ({vertical: [lead, ...]}) as produced by the selection step
and writes linked Company + Person under Mjeed.

The lead's review-derived pain hint is NOT stored in the CRM: it travels from the
scrape pool to the render via pipeline_prep.scrape_pain_index(), phone-matched. The
raw review text never ships in outreach copy either way — it only picks a pain
category downstream (see lina_compose.py's hard rule).

Usage:
    python scripts/import_selected_leads.py            # import
    python scripts/import_selected_leads.py --dry-run  # show what would be written
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import httpx

import nav_env

CRM = nav_env.crm_base()
# createdBy.name must contain "Mjeed" (the CRM hard rule keys ownership on that). The old
# value "Mjeed using " carried a trailing fragment; the agent tasks use a clean "Mjeed".
CREATED_BY = {"source": "AGENT", "name": "Mjeed", "context": {}}
ACTIVE = ["Real Estate", "Contracting & Facilities", "Training Institutes"]


def _phone_key(p: str) -> str:
    """Last 9 digits of a phone — comparable across +966 / 0 / bare-5 spellings."""
    return re.sub(r"\D", "", p or "")[-9:]


def existing_crm_phone_keys() -> set[str]:
    """Phone keys already on Mjeed's CRM people, via the PAGINATED helper.

    Dedup must see every one of the ~900 people; an unpaginated read silently truncates and
    would let the migration re-create leads that are already there (import_selected_leads has
    no upsert — a duplicate here is a duplicate in the shared CRM). Reuses
    pipeline_prep.crm_people_fields so the paging is not optional.
    """
    import pipeline_prep as prep
    keys = set()
    for person in prep.crm_people_fields("id phones{primaryPhoneNumber}"):
        num = ((person.get("phones") or {}).get("primaryPhoneNumber") or "").strip()
        if _phone_key(num):
            keys.add(_phone_key(num))
    return keys


def group_pool_by_vertical(pool: list[dict]) -> dict[str, list[dict]]:
    """The compact flat scrape list -> {vertical: [lead]} for ACTIVE verticals only.

    Leads already marked imported_crm (from a prior migration run) are skipped, so the
    migration is idempotent and drains the laptop pool run over run.
    """
    grouped: dict[str, list[dict]] = {v: [] for v in ACTIVE}
    for l in pool:
        sector = l.get("sector_guess")
        if sector in grouped and not l.get("imported_crm"):
            grouped[sector].append(l)
    return grouped


def headers() -> dict:
    return {"Authorization": "Bearer " + nav_env.env("TWENTY_TOKEN"), "Content-Type": "application/json"}


def intl_phone(p: str) -> str:
    """Saudi local -> E.164. 05xxxxxxxx -> +9665xxxxxxxx; 9200xxxxx stays national."""
    d = re.sub(r"\D", "", p or "")
    if d.startswith("966"):
        return "+" + d
    if d.startswith("05") and len(d) == 10:
        return "+966" + d[1:]
    if d.startswith("5") and len(d) == 9:
        return "+966" + d
    if d.startswith("011") and len(d) == 10:
        return "+966" + d[1:]
    return "+966" + d.lstrip("0") if d else ""


def lead_score(l: dict) -> int:
    """0-100, per the §11.5 rubric fields we can evidence from a scrape."""
    s = 0
    if l.get("website"):
        s += 20                      # active web presence
    if l.get("pain_hints"):
        s += 15                      # specific review-derived pain mapped
    try:
        rc = int(l.get("review_count") or 0)
        s += 20 if rc >= 200 else 15 if rc >= 100 else 10 if rc >= 30 else 5
    except ValueError:
        pass
    try:
        s += 15 if float(l.get("rating") or 0) >= 4.0 else 8
    except ValueError:
        pass
    if l.get("phone"):
        s += 20                      # reachable channel
    return min(s, 100)


def create_company(l: dict, vertical: str) -> str | None:
    body = {
        "name": l["name"],
        "address": {"addressStreet1": l.get("address", "")},
        "sector": vertical,
        "createdBy": CREATED_BY,
    }
    if (w := (l.get("website") or "").strip()):
        body["domainName"] = {"primaryLinkUrl": w if w.startswith("http") else "https://" + w}
    r = httpx.post(f"{CRM}/rest/companies", headers=headers(), json=body, timeout=30)
    if r.status_code not in (200, 201):
        print(f"    ERR company HTTP {r.status_code}: {r.text[:160]}")
        return None
    return r.json().get("data", {}).get("createCompany", {}).get("id")


def effective_phone(l: dict) -> str:
    """Person-first: the named person's mobile if enrichment found one, else the company phone.

    This is the phone/person doctrine (operator 2026-07-20) made concrete — a real person's
    number wins; the company number is only the fallback.
    """
    person = l.get("person") or {}
    return intl_phone(person.get("phone") or "") or intl_phone(l.get("phone", ""))


def create_person(l: dict, vertical: str, company_id: str) -> str | None:
    # Person-first: use the named contact from enrichment when present; otherwise fall back to
    # the company as the record (the old behaviour), so a lead with no named person still lands.
    person = l.get("person") or {}
    pname = (person.get("name") or "").strip()
    if pname:
        toks = pname.split()
        first, last = toks[0], " ".join(toks[1:])
    else:
        first, last = l["name"], ""
    body = {
        "name": {"firstName": first, "lastName": last},
        "companyId": company_id,
        "sector": vertical,
        "leadSource": l.get("lead_source", ""),
        "leadStatus": "Not Contacted",
        "leadScore": lead_score(l),
        "createdBy": CREATED_BY,
    }
    if (role := (person.get("role") or "").strip()):
        body["jobTitle"] = role
    if (ph := effective_phone(l)):
        body["phones"] = {"primaryPhoneNumber": ph}
    if (em := (person.get("email") or "").strip()):
        body["emails"] = {"primaryEmail": em}
    r = httpx.post(f"{CRM}/rest/people", headers=headers(), json=body, timeout=30)
    if r.status_code not in (200, 201):
        print(f"    ERR person HTTP {r.status_code}: {r.text[:160]}")
        return None
    return r.json().get("data", {}).get("createPerson", {}).get("id")


def import_from_pool(pool_path: str, dry_run: bool) -> None:
    """Migrate the enriched compact pool into the CRM, deduped and idempotent.

    - Person-first fields via create_person/effective_phone.
    - Dedup: skip any lead whose effective phone is ALREADY on a Mjeed CRM person (paginated
      read — import has no upsert, so a duplicate here is a real duplicate in the shared CRM).
    - Idempotent: every processed lead is marked imported_crm in the pool file (with the new
      ids, or {"skipped": "already_in_crm"}), so a re-run resumes and the laptop pool drains.
    """
    with io.open(pool_path, encoding="utf-8") as f:
        pool = json.load(f)
    grouped = group_pool_by_vertical(pool)
    pending = sum(len(v) for v in grouped.values())
    print(f"{pending} un-migrated active-vertical leads in {os.path.basename(pool_path)}")
    if not pending:
        print("nothing to migrate.")
        return

    existing = existing_crm_phone_keys()
    print(f"CRM already holds {len(existing)} Mjeed phone(s) — used for dedup.\n")

    made = skipped = 0
    for vertical, leads in grouped.items():
        print(f"=== {vertical} ({len(leads)}) ===")
        for l in leads:
            phone = effective_phone(l)
            key = _phone_key(phone)
            person = (l.get("person") or {}).get("name") or "(company record)"
            if key and key in existing:
                skipped += 1
                l["imported_crm"] = {"skipped": "already_in_crm", "phone": phone}
                print(f"  skip (in CRM)  {l['name'][:34]:34} {phone}")
                continue
            if dry_run:
                made += 1
                print(f"  DRY  {l['name'][:30]:30} | {phone or '-':15} | {person[:24]}")
                continue
            cid = create_company(l, vertical)
            if not cid:
                continue
            pid = create_person(l, vertical, cid)
            if not pid:
                continue
            made += 1
            if key:
                existing.add(key)          # prevent an intra-run duplicate too
            l["imported_crm"] = {"company_id": cid, "person_id": pid,
                                 "at": date.today().isoformat(), "phone": phone}
            print(f"  OK   {l['name'][:30]:30} | {phone or '-':15} | {person[:24]} "
                  f"| c{cid[:6]} p{pid[:6]}")
            time.sleep(0.5)                # CRM rate limit
        # persist after each vertical so an interruption never loses progress
        if not dry_run:
            with io.open(pool_path, "w", encoding="utf-8") as f:
                json.dump(pool, f, ensure_ascii=False, indent=1)

    verb = "would import" if dry_run else "imported"
    print(f"\n{verb}: {made} | skipped (already in CRM): {skipped} | "
          f"total considered: {made + skipped}")
    if not dry_run:
        print(f"marked in {os.path.basename(pool_path)} — re-run resumes where this left off.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--src", default="selected_leads.json")
    ap.add_argument("--from-pool", metavar="ENRICHED_JSON",
                    help="migrate the enriched compact pool (leads_enriched_people.json) instead "
                         "of selected_leads.json — deduped, person-first, idempotent")
    args = ap.parse_args()

    if args.from_pool:
        import_from_pool(args.from_pool, args.dry_run)
        return

    sel = json.load(open(args.src, encoding="utf-8"))
    made = 0
    for vertical, leads in sel.items():
        if vertical not in ACTIVE:
            print(f"SKIP retired/unknown vertical: {vertical}")
            continue
        print(f"\n=== {vertical} ===")
        for l in leads:
            score = lead_score(l)
            if args.dry_run:
                print(f"  DRY {l['name']} | {intl_phone(l['phone'])} | score {score} | {l.get('website','-')[:40]}")
                continue
            cid = create_company(l, vertical)
            if not cid:
                continue
            pid = create_person(l, vertical, cid)
            if not pid:
                continue
            made += 1
            print(f"  OK  {l['name']} | {intl_phone(l['phone'])} | score {score}")
            print(f"      company {cid[:8]} person {pid[:8]}")
            time.sleep(0.5)          # CRM rate limit
    print(f"\n{'would import' if args.dry_run else 'imported'}: {made if not args.dry_run else sum(len(v) for k,v in sel.items() if k in ACTIVE)} leads")


if __name__ == "__main__":
    main()

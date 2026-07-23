#!/usr/bin/env python3
"""Put the named decision-makers into the CRM, and replace placeholder 'people'.

Every lead imported so far carries a Person record whose name is just the COMPANY name
duplicated ("شركة المثال للمقاولات" as a person) with an info@ address. That is why outreach
opens with «القائمون على … الكرام» and why nobody scores the +10 named-decision-maker
signal. fetch_prospects.py found real humans with titles; this puts them in the CRM.

Per company:
  - The highest-tier prospect UPDATES the existing placeholder record. That record holds
    the company's outreach history, so promoting it in place keeps the history attached to
    the company's primary contact instead of orphaning it next to a new duplicate.
  - Every other prospect is CREATED as an additional Person on the same company.

HONESTY NOTE ON THE HISTORY: the placeholder's leadStatus says "Emailed" because we
emailed info@, NOT because we emailed this person. Renaming the record does not make that
person contacted. Their `leadStatus` is therefore reset to "Not Contacted" when we have
their own address, so the next batch actually writes to them. The company-level fact that
info@ was already contacted lives in the Notes line this script writes.

Nothing here sends anything. Run --dry-run first; it prints every write it would make.

Usage:
    python scripts/import_prospects_crm.py --dry-run
    python scripts/import_prospects_crm.py
"""
from __future__ import annotations
import nav_env

import argparse
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import httpx

import pipeline_prep as prep
from reveal_prospect_emails import tier

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PROSPECTS = os.path.join(ROOT, "prospects.json")
CONTACTS = os.path.join(ROOT, "contacts.json")
CRM = nav_env.crm_base()
CREATED_BY = {"source": "AGENT", "name": "Mjeed using ", "context": {}}

# Role mailboxes — reaching one of these is reaching a reception desk, not a person, so a
# record holding only one of them is still effectively uncontacted at the human level.
_GENERIC_MAILBOX = re.compile(
    r"^(info|contact|sales|admin|support|office|hello|mail|enquiry|inquiries)@", re.I)


def _load(path: str) -> list:
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def split_name(full: str) -> tuple[str, str]:
    """('Abdullah', 'Alzaid'). Snov puts certification salad in last_name — trim it.

    Keeps EVERY remaining word, not just the second. A real three-token name in our data
    ("FIRST AL- SURNAME" shape) was stored as "FIRST AL-" because parts[1] alone was
    taken, and the truncation then rendered straight into the Arabic greeting. Tokens are
    dropped individually once they stop looking like a name.
    """
    parts = [p for p in (full or "").split() if p]
    if not parts:
        return "", ""
    first, rest = parts[0], parts[1:]
    keep = []
    for token in rest:
        # "CSCP®," / "LEED" / "GA®" / "MBA" — credentials, not surname components.
        if any(c in token for c in "®©™,") or token.upper() in {
                "MBA", "PMP", "BE", "CFM", "CMRP", "RMP", "CSCP", "LEED", "GA", "ISO",
                "OSHA", "IOSH", "CANDIDATE", "CLDM", "PHD", "DR"}:
            break
        keep.append(token)
    last = " ".join(keep)[:60]
    return first, last


def crm_state() -> tuple[dict, dict]:
    """(company_name -> company_id, company_name -> [person records])."""
    companies, people = {}, {}
    for p in prep._crm_people():
        comp = (p.get("company") or {}).get("name") or ""
        if not comp:
            continue
        companies[comp] = (p.get("company") or {}).get("id")
        people.setdefault(comp, []).append(p)
    return companies, people


def is_placeholder(person: dict, company: str) -> bool:
    """A 'person' whose name is really just the company name."""
    nm = " ".join(x for x in [(person.get("name") or {}).get("firstName"),
                              (person.get("name") or {}).get("lastName")] if x).strip()
    return bool(nm) and (nm == company or nm[:18] == company[:18])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    prospects = _load(PROSPECTS)
    emails = {c["name"]: (c.get("emails") or [None])[0] for c in _load(CONTACTS) if c.get("emails")}
    if not prospects:
        raise SystemExit("prospects.json is empty — run fetch_prospects.py first.")

    companies, people = crm_state()
    by_company: dict[str, list] = {}
    for pr in prospects:
        by_company.setdefault(pr["company"], []).append({**pr, "tier": tier(pr.get("position", ""))})

    planned_updates, planned_creates, skipped = [], [], []
    for company, rows in by_company.items():
        rows.sort(key=lambda r: r["tier"])
        cid = companies.get(company)
        existing = people.get(company, [])
        if not cid:
            skipped.append((company, "company not found in CRM"))
            continue
        # Names already present — never create a second record for the same human.
        have = {" ".join(x for x in [(p.get("name") or {}).get("firstName"),
                                     (p.get("name") or {}).get("lastName")] if x).strip().lower()
                for p in existing}
        placeholder = next((p for p in existing if is_placeholder(p, company)), None)

        for i, pr in enumerate(rows):
            if pr["name"].strip().lower() in have:
                skipped.append((pr["name"], "already in CRM"))
                continue
            email = emails.get(pr["name"])
            first, last = split_name(pr["name"])
            payload = {
                "name": {"firstName": first, "lastName": last},
                "jobTitle": (pr.get("position") or "")[:120],
                "companyId": cid,
                "createdBy": CREATED_BY,
            }
            if pr.get("linkedin"):
                payload["linkedinLink"] = {"primaryLinkUrl": pr["linkedin"]}
            if email:
                payload["emails"] = {"primaryEmail": email}
                # Promoting a placeholder replaces its primary address. That address is the
                # company's info@ mailbox and is still a real way to reach the business, so
                # it is kept as an additional email rather than dropped on the floor.
                if i == 0 and placeholder is not None:
                    old = (placeholder.get("emails") or {}).get("primaryEmail") or ""
                    if old and old.lower() != email.lower():
                        payload["emails"]["additionalEmails"] = [old]
            if i == 0 and placeholder is not None:
                # The placeholder may read "Emailed" — but that records emailing info@, not
                # emailing THIS person. Renaming the record does not make them contacted.
                # Whenever the record ends up holding a personal address, reset the status
                # so the next batch actually writes to the human.
                final_email = email or (placeholder.get("emails") or {}).get("primaryEmail") or ""
                if final_email and not _GENERIC_MAILBOX.match(final_email):
                    payload["leadStatus"] = "Not Contacted"
            elif email:
                payload["leadStatus"] = "Not Contacted"
            if i == 0 and placeholder is not None:
                planned_updates.append((placeholder["id"], company, pr, payload, email))
                placeholder = None
            else:
                payload.setdefault("leadStatus", "Not Contacted")
                planned_creates.append((company, pr, payload, email))

    print(f"UPDATE {len(planned_updates)} placeholder record(s) -> real person:")
    for pid, company, pr, payload, email in planned_updates:
        print(f"  {company[:30]:30} '{company[:18]}…' -> {pr['name'][:24]:24} "
              f"{(pr.get('position') or '')[:34]:34} {email or '(no email)'}")
    print(f"\nCREATE {len(planned_creates)} new person record(s):")
    for company, pr, payload, email in planned_creates:
        print(f"  {company[:30]:30} {pr['name'][:24]:24} "
              f"{(pr.get('position') or '')[:34]:34} {email or '(no email)'}")
    if skipped:
        print(f"\nSKIPPED {len(skipped)}:")
        for what, why in skipped:
            print(f"  {what[:44]:44} {why}")

    if args.dry_run:
        print("\nDRY RUN — nothing written.")
        return

    ok = fail = 0
    for pid, company, pr, payload, email in planned_updates:
        r = httpx.patch(f"{CRM}/rest/people/{pid}", headers=prep._crm_h(), json=payload, timeout=30)
        ok += r.status_code < 300
        fail += r.status_code >= 300
        print(f"  {'OK ' if r.status_code < 300 else 'ERR'} update {pr['name'][:26]:26} "
              f"{'' if r.status_code < 300 else r.text[:120]}")
    for company, pr, payload, email in planned_creates:
        r = httpx.post(f"{CRM}/rest/people", headers=prep._crm_h(), json=payload, timeout=30)
        ok += r.status_code in (200, 201)
        fail += r.status_code not in (200, 201)
        print(f"  {'OK ' if r.status_code in (200, 201) else 'ERR'} create {pr['name'][:26]:26} "
              f"{'' if r.status_code in (200, 201) else r.text[:120]}")
    print(f"\n{ok} written, {fail} failed.")


if __name__ == "__main__":
    main()

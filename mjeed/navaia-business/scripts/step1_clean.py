#!/usr/bin/env python3
"""
Step 1: Fix encoding, validate phones/addresses/domains, write clean CSV.
No API calls — runs instantly.
"""

import csv
import re

INPUT_CSV = "/app/workspace/leads.csv"
OUTPUT_CSV = "/app/workspace/leads_clean.csv"


# This script runs in the cloud runtime, where scripts/ may not be installed yet
# (see cloud_bootstrap.py). Use the shared rule when it is importable; the inline
# fallback must stay in sync with pipeline_prep._NOT_OWN_DOMAIN.
try:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from pipeline_prep import _domain_of as extract_domain
except Exception:
    _NOT_OWN = re.compile(
        r"(^|\.)(aqar\.fm|bayut\.[a-z.]+|haraj\.com\.sa|opensooq\.com|glitch\.me|"
        r"blogspot\.[a-z.]+|wordpress\.com|wix(site)?\.com|weebly\.com|godaddysites\.com|"
        r"sites\.google\.com|business\.site|linktr\.ee|facebook\.com|instagram\.com|"
        r"twitter\.com|x\.com|linkedin\.com|tiktok\.com|snapchat\.com|youtube\.com|"
        r"wa\.me|whatsapp\.com|google\.com|maps\.app\.goo\.gl)$", re.I)

    def extract_domain(url):
        if not url or not url.strip():
            return ""
        domain = re.sub(r"^https?://", "", url.strip())
        domain = re.sub(r"^www\.", "", domain).split("/")[0].split(":")[0].lower().strip()
        if "." not in domain or _NOT_OWN.search(domain):
            return ""
        return domain


def validate_phone(phone):
    if not phone or not phone.strip():
        return False
    phone = phone.strip()
    if re.match(r"^\+966\s?\d{1,2}\s?\d{3}\s?\d{4}$", phone):
        return True
    if re.match(r"^\+966\s?800\s?\d{3}\s?\d{4}$", phone):
        return True
    if re.match(r"^\+966\s?9200\s?\d{5}$", phone):
        return True
    if re.match(r"^\+\d{1,4}\s?\d{1,4}\s?\d{3,4}\s?\d{3,4}$", phone):
        return True
    return False


def validate_address(address):
    if not address:
        return False
    if "riyadh" in address.lower() or "الرياض" in address:
        return True
    return False


def is_garbled(text):
    if not text:
        return False
    if any(c in text for c in ["Ø", "Ù", "Ø´", "Ø§", "Ù„", "Ø©", "\ufffd"]):
        return True
    return False


def clean_name(name):
    if not name:
        return name
    if is_garbled(name):
        parts = re.split(r"[\u00d8\u00d9\u00da\u00db\u00dc\u0600-\u06ff\ufffd]", name)
        clean_parts = [p.strip() for p in parts if p.strip() and not is_garbled(p) and len(p.strip()) > 1]
        if clean_parts:
            return " ".join(clean_parts).strip()
    return name.strip()


def main():
    with open(INPUT_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        leads = list(reader)

    print(f"Loaded {len(leads)} leads")

    stats = {"total": len(leads), "phones_ok": 0, "addresses_ok": 0,
             "domains_ok": 0, "domains_missing": 0, "garbled_fixed": 0, "removed": 0}

    clean_leads = []

    for i, lead in enumerate(leads):
        company_raw = lead.get("company_name", "")
        company = clean_name(company_raw)

        if company != company_raw:
            stats["garbled_fixed"] += 1
            print(f"[{i+1}] FIXED: '{company_raw[:50]}' -> '{company[:50]}'")
        else:
            print(f"[{i+1}] {company[:60]}")

        # Validate phone
        phone = lead.get("phone", "")
        if not validate_phone(phone):
            stats["removed"] += 1
            print(f"  SKIP: invalid phone")
            continue
        stats["phones_ok"] += 1

        # Validate address
        address = lead.get("address", "")
        if not validate_address(address):
            stats["removed"] += 1
            print(f"  SKIP: invalid address")
            continue
        stats["addresses_ok"] += 1

        # Domain
        domain = extract_domain(lead.get("domain_name", ""))
        domain_ok = bool(domain) and bool(re.match(
            r"^[a-z0-9]([a-z0-9\-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]*[a-z0-9])?)+$", domain
        ))
        if domain_ok:
            stats["domains_ok"] += 1
        else:
            stats["domains_missing"] += 1

        print(f"  Phone OK | Address OK | Domain: {domain or '(none)'}")

        clean_leads.append({
            "company_name": company,
            "domain_name": domain,
            "address": address,
            "phone": phone,
            "email": "",
            "email_status": "not_found",
            "sector": lead.get("sector", ""),
            "vertical_tier": lead.get("vertical_tier", ""),
            "created_by": "Mjeed using [Tariq SDR Agent]",
            "lead_source": "Google-Places",
            "place_id": lead.get("place_id", ""),
        })

    fieldnames = ["company_name", "domain_name", "address", "phone",
                  "email", "email_status", "sector", "vertical_tier",
                  "created_by", "lead_source", "place_id"]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(clean_leads)

    print(f"\n{'='*50}")
    print(f"Clean CSV: {OUTPUT_CSV}")
    print(f"Kept: {len(clean_leads)} / {stats['total']}")
    print(f"Removed: {stats['removed']}")
    print(f"Garbled fixed: {stats['garbled_fixed']}")
    print(f"Phones OK: {stats['phones_ok']}")
    print(f"Addresses OK: {stats['addresses_ok']}")
    print(f"Domains OK: {stats['domains_ok']}")
    print(f"Domains missing: {stats['domains_missing']}")


if __name__ == "__main__":
    main()

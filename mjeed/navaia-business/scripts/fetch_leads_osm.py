#!/usr/bin/env python3
"""
FALLBACK lead source: OpenStreetMap via the Overpass API (free, no key, no
account). Writes the same CSV schema as fetch_leads.py so the downstream
pipeline (clean -> enrich -> verify -> import) is unchanged.
lead_source = "Overpass-OSM"; place_id holds the OSM id (e.g. "node/123").

Reality check (probed 2026-07-14): OSM coverage for Riyadh SMBs is THIN —
~180 relevant POIs, ~30 with phones, across all 5 verticals. This is a
supplement / fallback only. The PRIMARY keyless source is the self-hosted
open-source Google Maps scraper (gosom/google-maps-scraper) — see
workforce/playbooks/lead_pipeline.md. Google Places API itself is retired
(needs a CNTXT corporate account in Saudi as of 2026).

Overpass etiquette: ONE combined query per run (not per vertical), bbox not
around:, [timeout:120], rotate endpoints on 429/504, never hammer-retry.
"""

import csv
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
OUTPUT_CSV = os.environ.get("OUTPUT_CSV", os.path.join(os.path.dirname(__file__), "..", "leads_osm.csv"))

# Riyadh bbox (south,west,north,east) — cheaper for Overpass than around:50000
BBOX = "24.30,46.20,25.15,47.10"

# One combined query: every POI type we can classify, phone required in-tag
# (phone or contact:phone) so we never download phoneless noise.
QUERY = f"""[out:json][timeout:120][bbox:{BBOX}];
(
  nwr["office"~"estate_agent|property_management|construction|facility_management|financial|educational_institution|company"]["phone"];
  nwr["office"~"estate_agent|property_management|construction|facility_management|financial|educational_institution|company"]["contact:phone"];
  nwr["amenity"~"^(dentist|clinic|training)$"]["phone"];
  nwr["amenity"~"^(dentist|clinic|training)$"]["contact:phone"];
  nwr["healthcare"~"dentist|physiotherapist|clinic"]["phone"];
  nwr["healthcare"~"dentist|physiotherapist|clinic"]["contact:phone"];
);
out tags center;"""

# Arabic/English name keywords for classifying generic POIs (office=company etc.)
NAME_KEYWORDS = {
    "Contracting & Facilities": ["مقاولات", "صيانة", "مرافق", "contracting", "maintenance", "facilit"],
    "Finance & Debt Collection": ["تحصيل", "تمويل", "تقسيط", "debt", "collection", "finance", "installment"],
    "Private Clinics": ["أسنان", "جلدية", "تجميل", "علاج طبيعي", "dental", "derma", "cosmetic", "physio"],
    "Real Estate": ["عقار", "أملاك", "real estate", "property"],
    "Training Institutes": ["تدريب", "معهد", "training", "institute"],
}
TIERS = {
    "Contracting & Facilities": "Tier 1",
    "Finance & Debt Collection": "Tier 1",
    "Private Clinics": "Tier 1",
    "Real Estate": "Tier 2",
    "Training Institutes": "Tier 2",
}


def classify(tags, name):
    """Map OSM tags (or, for generic tags, the business name) to a vertical."""
    office = tags.get("office", "")
    amenity = tags.get("amenity", "")
    healthcare = tags.get("healthcare", "")
    speciality = tags.get("healthcare:speciality", "")
    lname = name.lower()

    if office in ("estate_agent", "property_management"):
        return "Real Estate"
    if office in ("construction", "construction_company", "facility_management"):
        return "Contracting & Facilities"
    if office == "financial":
        return "Finance & Debt Collection"
    if office == "educational_institution" or amenity == "training":
        return "Training Institutes"
    if amenity == "dentist" or healthcare in ("dentist", "physiotherapist"):
        return "Private Clinics"
    if amenity == "clinic" or healthcare == "clinic":
        # Only specialty clinics are in scope — require a speciality or name signal
        if any(s in speciality for s in ("dermatology", "cosmetic", "physiotherapy", "dentist")):
            return "Private Clinics"
        if any(k in lname for k in NAME_KEYWORDS["Private Clinics"]):
            return "Private Clinics"
        return None
    # Generic office=company — classify by name keywords, else skip
    for sector, kws in NAME_KEYWORDS.items():
        if any(k in lname for k in kws):
            return sector
    return None


def run_query():
    data = urllib.parse.urlencode({"data": QUERY}).encode("utf-8")
    last_err = None
    for url in ENDPOINTS:
        req = urllib.request.Request(url, data=data, method="POST",
                                     headers={"User-Agent": "navaia-lead-fetch/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last_err = e
            print(f"  {url} failed ({e}) — trying next endpoint")
            time.sleep(5)
    raise SystemExit(f"All Overpass endpoints failed; try later. Last error: {last_err}")


def main():
    result = run_query()
    all_leads = []
    seen_ids = set()
    seen_names = set()

    for el in result.get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("name:ar") or tags.get("name:en") or ""
        phone = tags.get("phone") or tags.get("contact:phone") or ""
        if not name or not phone:
            continue
        sector = classify(tags, name)
        if sector is None:
            continue
        osm_id = f"{el.get('type')}/{el.get('id')}"
        cname = name.lower().strip()
        if osm_id in seen_ids or cname in seen_names:
            continue
        seen_ids.add(osm_id)
        seen_names.add(cname)
        website = tags.get("website") or tags.get("contact:website") or ""
        street = tags.get("addr:street", "")
        city = tags.get("addr:city", "Riyadh")
        all_leads.append({
            "company_name": name,
            "domain_name": website,
            "address": ", ".join(p for p in (street, city) if p) or "Riyadh",
            "phone": phone,
            "sector": sector,
            "vertical_tier": TIERS[sector],
            "created_by": "Mjeed using [Tariq SDR Agent]",
            "lead_source": "Overpass-OSM",
            "place_id": osm_id,
        })
        print(f"  + [{sector}] {name} | {phone}")

    out_dir = os.path.dirname(os.path.abspath(OUTPUT_CSV))
    os.makedirs(out_dir, exist_ok=True)
    fieldnames = ["company_name", "domain_name", "address", "phone", "sector",
                  "vertical_tier", "created_by", "lead_source", "place_id"]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_leads)

    print(f"\n{'=' * 60}")
    print(f"TOTAL LEADS: {len(all_leads)}")
    print(f"CSV written to: {OUTPUT_CSV}")
    for sector in TIERS:
        n = sum(1 for l in all_leads if l["sector"] == sector)
        print(f"  {sector}: {n}")


if __name__ == "__main__":
    main()

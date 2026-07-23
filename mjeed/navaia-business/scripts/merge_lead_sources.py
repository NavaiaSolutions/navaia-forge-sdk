#!/usr/bin/env python3
"""Couple the two keyless lead sources into ONE deduped pool.

The Google Places API is retired (CNTXT-only in Saudi). Its replacement is the
self-hosted `gosom/google-maps-scraper`, which carries depth Overpass cannot:
websites, review counts, and the review text that feeds trust-locked pain lines.
Overpass/OSM is thin on its own (~6 phone-bearing Riyadh SMBs in a 2026-07-19
probe) but it is keyless, runs anywhere, and surfaces registered offices whose
Maps listing the query terms miss.

Treating OSM as a mere fallback wastes it. This merges BOTH into one pool:
gosom rows win on conflict (richer fields), OSM rows are additive.

Dedupe key, in priority order:
  1. normalized phone (last 9 digits) — the strongest signal across sources
  2. normalized company name (diacritics/legal-form stripped)

Usage:
    python scripts/merge_lead_sources.py <gosom.csv> <osm.csv> [out.json]
"""

import csv
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
csv.field_size_limit(10_000_000)

# NOTE: import BEFORE re-wrapping stdout. distill_scraped_leads rebinds sys.stdout at
# module level; wrapping first means two TextIOWrappers over one buffer, and whichever
# is collected first closes it out from under the other ("I/O operation on closed file").
from distill_scraped_leads import guess_sector, pain_hints, RETIRED_KEYWORDS  # vertical truth


def is_retired(sector: str) -> bool:
    """True for both forms a retired vertical can arrive in.

    gosom rows go through guess_sector() and carry the 'RETIRED:<name>' prefix, but OSM
    rows carry their sector verbatim from the CSV ('Private Clinics') and would otherwise
    bypass the lock entirely — which they did on the first run.
    """
    s = (sector or "").strip()
    return s.startswith("RETIRED:") or s in RETIRED_KEYWORDS

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_LEGAL = ["شركة", "مؤسسة", "مكتب", "معهد", "مركز", "co.", "llc", "ltd", "inc"]


def norm_phone(p: str) -> str:
    d = re.sub(r"\D", "", p or "")
    return d[-9:] if len(d) >= 9 else ""


def norm_name(n: str) -> str:
    s = (n or "").lower().strip()
    s = re.sub(r"[ً-ْ]", "", s)          # Arabic diacritics
    for w in _LEGAL:
        s = s.replace(w, "")
    return re.sub(r"[^\w؀-ۿ]+", "", s)


def _keys(lead: dict) -> list[str]:
    out = []
    if (ph := norm_phone(lead.get("phone", ""))):
        out.append("p:" + ph)
    if (nm := norm_name(lead.get("name", ""))):
        out.append("n:" + nm)
    return out


def load_gosom(path: str) -> list[dict]:
    leads = []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            name, phone = (row.get("title") or "").strip(), (row.get("phone") or "").strip()
            if not name or not phone:
                continue
            leads.append({
                "name": name,
                "sector_guess": guess_sector(name, row.get("category") or ""),
                "category": (row.get("category") or "").strip(),
                "address": (row.get("address") or "").strip(),
                "phone": phone,
                "website": (row.get("website") or "").strip(),
                "rating": row.get("review_rating") or "",
                "review_count": row.get("review_count") or "",
                "place_id": row.get("place_id") or "",
                "pain_hints": pain_hints(row),
                "lead_source": "Google-Maps-Scraper",
            })
    return leads


def load_osm(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    leads = []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("company_name") or "").strip()
            phone = (row.get("phone") or "").strip()
            if not name or not phone:
                continue
            leads.append({
                "name": name,
                "sector_guess": (row.get("sector") or "").strip(),
                "category": "",
                "address": (row.get("address") or "").strip(),
                "phone": phone,
                "website": (row.get("domain_name") or "").strip(),
                "rating": "",
                "review_count": "",
                "place_id": row.get("place_id") or "",
                "pain_hints": [],
                "lead_source": "Overpass-OSM",
            })
    return leads


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("usage: merge_lead_sources.py <gosom.csv> <osm.csv> [out.json]")
    dst = sys.argv[3] if len(sys.argv) > 3 else "leads_scraped_compact.json"

    gos, osm = load_gosom(sys.argv[1]), load_osm(sys.argv[2])
    pool: list[dict] = []
    seen: set[str] = set()
    stats = {"gosom": 0, "osm_new": 0, "osm_dup": 0, "retired": 0}

    for src, lead in [("gosom", l) for l in gos] + [("osm", l) for l in osm]:
        if is_retired(lead["sector_guess"]):
            stats["retired"] += 1
            continue
        ks = _keys(lead)
        if any(k in seen for k in ks):
            if src == "osm":
                stats["osm_dup"] += 1
            continue
        seen.update(ks)
        pool.append(lead)
        stats["gosom" if src == "gosom" else "osm_new"] += 1

    with open(dst, "w", encoding="utf-8") as f:
        json.dump(pool, f, ensure_ascii=False, indent=1)

    by_sector: dict[str, int] = {}
    for l in pool:
        by_sector[l["sector_guess"] or "(unclassified)"] = by_sector.get(l["sector_guess"] or "(unclassified)", 0) + 1

    print(f"MERGED POOL: {len(pool)} leads -> {dst}")
    print(f"  from gosom (Google Maps) : {stats['gosom']}")
    print(f"  from OSM, net new        : {stats['osm_new']}")
    print(f"  OSM rows deduped away    : {stats['osm_dup']}")
    print(f"  dropped, RETIRED vertical: {stats['retired']}")
    print("by vertical:")
    for s, n in sorted(by_sector.items(), key=lambda x: -x[1]):
        print(f"  {s}: {n}")
    withweb = sum(1 for l in pool if l["website"])
    withpain = sum(1 for l in pool if l["pain_hints"])
    print(f"enrichable: {withweb} have a website (email path), {withpain} carry review-derived pain hints")


if __name__ == "__main__":
    main()

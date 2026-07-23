"""Trust-locked review enrichment — derive each lead's specific pain from its OWN Google
reviews, and append it to the EXACT lead in the CRM.

TRUST RULES (do not weaken):
  1. Match by Google Places `place_id` ONLY — never a name search. This guarantees we read
     the reviews of THIS exact business, not a similarly-named one.
  2. Verify the Places phone == the lead's phone. If they don't match, SKIP the lead
     (untrusted / possible data mismatch). No phone on the place -> skip.
  3. Reason the pain ONLY from the actual review text (cheap model). Never invent a pain the
     reviews don't support. No reviews -> no pain, skip.

Flow per lead (needs place_id + phone):
  Places Details (place_id) -> reviews + phone -> verify phone -> cheap-model derive one
  short Arabic pain/inbound-context line -> write to leads_reviews.csv (keyed by place_id)
  + find company in CRM by name+address match -> add pain as Note. Feeds {trigger_line}.

Reads from .env: PLACES_API (Places Details), OPENROUTER_API_KEY (cheap model), TWENTY_TOKEN
(CRM write). Run on-demand; schedule a refresh later.

Usage:
    python scripts/enrich_reviews.py --in leads_enriched.csv
    python scripts/enrich_reviews.py --in leads_enriched.csv --limit 10 --no-crm
"""
from __future__ import annotations
import nav_env

import argparse
import csv
import datetime as _dt
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.join(os.path.dirname(__file__), "..")
CHEAP_MODEL = "qwen/qwen3.6-plus"   # cheap model — the only OpenRouter cost here (~$0.0004/lead)
PLACES_DETAILS = "https://places.googleapis.com/v1/places/"


def _env(key: str) -> str | None:
    v = os.environ.get(key)
    if v:
        return v
    try:
        m = re.search(rf"^{re.escape(key)}=(.+)$", open(os.path.join(ROOT, ".env")).read(), re.M)
        return m.group(1).strip() if m else None
    except OSError:
        return None


def _norm_phone(p: str) -> str:
    return re.sub(r"\D", "", p or "")


def place_details(place_id: str, key: str) -> dict:
    """Fetch reviews + phone + address for an EXACT place_id (new Places API)."""
    req = urllib.request.Request(
        PLACES_DETAILS + urllib.parse.quote(place_id),
        headers={
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": "id,displayName,internationalPhoneNumber,reviews,formattedAddress",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.load(r)
    except Exception as e:
        print(f"    (places error: {e})")
        return {}


def derive_pain(company: str, reviews: list[str], key: str) -> str:
    """Cheap model: ONE short Arabic pain line grounded ONLY in the reviews, or empty."""
    if not reviews:
        return ""
    joined = "\n".join(f"- {r}" for r in reviews[:6])
    prompt = (
        f"Business: {company}\nIts Google reviews:\n{joined}\n\n"
        "From THESE reviews only, identify the single operational pain most relevant to "
        "customer-response / missed-inquiry automation (e.g. slow or no reply, missed calls, "
        "hard to book, long wait). Return JSON: {\"pain\": \"<ONE short Arabic sentence stating "
        "that pain as a known, fixable pain in their line of work — WITHOUT any attribution to "
        "reviews or feedback. NEVER write 'لاحظت أن مراجعيكم ذكروا' or mention تقييمات/مراجعات; "
        "e.g. 'تأخّر الردّ على اتصالات العملاء ورسائلهم في أوقات الذروة'>\"}. The reviews only "
        "PICK the pain; the sentence must read as if we simply know the field. If the reviews "
        "show no such pain, return {\"pain\": \"\"}. Do NOT invent anything the reviews don't say."
    )
    body = json.dumps({"model": CHEAP_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.1}).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            txt = json.load(r)["choices"][0]["message"]["content"]
        m = re.search(r"\{.*\}", txt, re.S)
        return str(json.loads(m.group(0)).get("pain", "")).strip() if m else ""
    except Exception as e:
        print(f"    (model error: {e})")
        return ""


def update_lead_by_place_id(place_id: str, pain: str, pain_date: str, token: str) -> bool:
    """Update a lead by place_id using PATCH, preserving createdBy. Returns True if successful."""
    import httpx
    base_url = nav_env.crm_base()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # First, get the current lead data to preserve createdBy
    try:
        # Query to find company by place_id
        query = '''
        query FindCompanyByPlaceId($placeId: String!) {
          companies(filter: { customFields: { place_id: { eq: $placeId } } }, first: 1) {
            edges {
              node {
                id
                name
                customFields
                createdBy
              }
            }
          }
        }
        '''
        
        resp = httpx.post(
            f"{base_url}/graphql",
            headers=headers,
            json={"query": query, "variables": {"placeId": place_id}},
            timeout=30
        )
        
        if resp.status_code != 200:
            print(f"    (CRM query error: {resp.status_code})")
            return False
            
        data = resp.json()
        companies = data.get("data", {}).get("companies", {}).get("edges", [])
        
        if not companies:
            print(f"    (Company not found for place_id: {place_id})")
            return False
            
        company = companies[0]["node"]
        company_id = company["id"]
        
        # Preserve the original createdBy field
        created_by = company.get("createdBy", {"source": "AGENT", "name": "Mjeed", "context": {}})
        
        # Prepare the update payload with preserved createdBy
        payload = {
            "name": company["name"],
            "customFields": {
                **company.get("customFields", {}),
                "pain_line": pain,
                "pain_date": pain_date
            },
            "createdBy": created_by
        }
        
        # Update the company using PATCH
        update_resp = httpx.patch(
            f"{base_url}/rest/companies/{company_id}",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if update_resp.status_code == 200:
            return True
        else:
            print(f"    (CRM update error: {update_resp.status_code}, {update_resp.text})")
            return False
            
    except Exception as e:
        print(f"    (CRM update error: {e})")
        return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="leads CSV — UPDATED in place (adds pain_line)")
    ap.add_argument("--limit", type=int, default=0, help="cap leads processed this run (0 = all)")
    ap.add_argument("--refresh", action="store_true", help="re-derive even if a pain_line already exists")
    ap.add_argument("--no-crm", action="store_true", help="skip CRM write (CSV only)")
    args = ap.parse_args()

    places_key = _env("PLACES_API")
    or_key = _env("OPENROUTER_API_KEY")
    crm_token = _env("TWENTY_TOKEN")
    if not (places_key and or_key):
        raise SystemExit("Need PLACES_API and OPENROUTER_API_KEY (env or .env)")

    with open(args.inp, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    fields = list(rows[0].keys()) if rows else []
    for col in ("pain_line", "pain_date"):
        if col not in fields:
            fields.append(col)

    today = _dt.date.today().isoformat()
    todo = rows[: args.limit] if args.limit else rows
    processed = derived = crm_updated = 0
    for i, r in enumerate(todo, 1):
        company = r.get("company_name") or r.get("name", "")
        # Idempotent + cost-friendly: skip anything already enriched, or without a trusted key.
        if r.get("pain_line") and not args.refresh:
            continue
        pid = (r.get("place_id") or "").strip()
        lead_phone = _norm_phone(r.get("phone", ""))
        if not pid or not lead_phone:
            continue
        processed += 1

        d = place_details(pid, places_key)
        place_phone = _norm_phone(d.get("internationalPhoneNumber", ""))
        place_address = d.get("formattedAddress", "")
        # TRUST GATE: exact place_id + the phone must match (never a similar-name company).
        matched = bool(place_phone) and (place_phone.endswith(lead_phone[-9:]) or lead_phone.endswith(place_phone[-9:]))
        if not matched:
            print(f"[{i}] {company}: skip (phone mismatch: place={place_phone or '—'} vs lead={lead_phone})")
            continue
        reviews = [((rv.get("text") or {}).get("text") or "").strip() for rv in d.get("reviews", [])]
        reviews = [x for x in reviews if x]
        pain = derive_pain(company, reviews, or_key)   # only qwen call — and only for a trusted lead with reviews
        r["pain_line"] = pain
        r["pain_date"] = today if pain else ""
        if pain:
            derived += 1
            print(f"[{i}] {company}: {pain}")
            
            # CRM write: update lead by place_id using PATCH, preserving createdBy
            if not args.no_crm and crm_token:
                if update_lead_by_place_id(pid, pain, today, crm_token):
                    crm_updated += 1
                    print(f"    -> CRM lead updated")
                else:
                    print(f"    -> CRM update FAILED")
        time.sleep(1.0)

    # Write the whole file back, preserving every column + the filled pain_line.
    with open(args.inp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    skipped = len(todo) - processed
    print(f"\nupdated {os.path.basename(args.inp)}: {derived} pains derived, {processed} processed, "
          f"{skipped} skipped (already-enriched or no place_id/phone).")
    if not args.no_crm:
        print(f"CRM Notes added: {crm_updated}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Cross-language duplicate check for newly imported companies.

Checks each of the 36 new companies against ALL 645 CRM companies using:
1. Domain match (definitive)
2. Phone match (definitive — fetched from contacts)
3. Address overlap (strong signal)
4. Cross-language name matching (Arabic vs English transliteration)

This catches cases like "Al Rashid Trading" vs "الرشيد للتجارة" being the same company.
"""
import sys, io, re, json, csv, time
import nav_env
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import httpx

env_content = open('C:/Users/aabbo/navaia-forge-sdk/.env').read()
token = re.search(r'TWENTY_TOKEN=(.+)', env_content).group(1).strip()
base_url = nav_env.crm_base()
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Load the 36 imported leads
with open('C:/Users/aabbo/navaia-forge-sdk/leads_enriched.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    imported_leads = list(reader)

print(f"Loaded {len(imported_leads)} imported leads\n", flush=True)

# === 1. Fetch ALL companies from CRM via GraphQL ===
print("Fetching all companies from CRM...", flush=True)
all_companies = []
cursor = None
page = 0

query = """
query GetCompanies($first: Int!, $after: String) {
  companies(first: $first, after: $after) {
    edges {
      node {
        id
        name
        domainName { primaryLinkUrl }
        address { addressStreet1 addressCity }
        createdAt
      }
    }
    pageInfo { hasNextPage endCursor }
    totalCount
  }
}
"""

while True:
    variables = {"first": 100}
    if cursor:
        variables["after"] = cursor
    resp = httpx.post(f"{base_url}/graphql", headers=headers,
                      json={"query": query, "variables": variables}, timeout=60)
    data = resp.json().get("data", {}).get("companies", {})
    edges = data.get("edges", [])
    for edge in edges:
        all_companies.append(edge["node"])
    page_info = data.get("pageInfo", {})
    page += 1
    print(f"  Page {page}: {len(edges)} (total: {len(all_companies)}/{data.get('totalCount', 0)})", flush=True)
    if page_info.get("hasNextPage"):
        cursor = page_info.get("endCursor")
        time.sleep(0.3)
    else:
        break

print(f"\nTotal CRM companies: {len(all_companies)}\n", flush=True)

# === 2. Fetch ALL people (contacts) to get phone numbers ===
print("Fetching all contacts from CRM...", flush=True)
all_people = []
cursor = None
page = 0

query_people = """
query GetPeople($first: Int!, $after: String) {
  people(first: $first, after: $after) {
    edges {
      node {
        id
        name { firstName lastName }
        phones { primaryPhoneNumber }
        emails { primaryEmail }
        companyId
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

while True:
    variables = {"first": 100}
    if cursor:
        variables["after"] = cursor
    resp = httpx.post(f"{base_url}/graphql", headers=headers,
                      json={"query": query_people, "variables": variables}, timeout=60)
    data = resp.json().get("data", {}).get("people", {})
    edges = data.get("edges", [])
    for edge in edges:
        all_people.append(edge["node"])
    page_info = data.get("pageInfo", {})
    page += 1
    print(f"  Page {page}: {len(edges)} (total: {len(all_people)})", flush=True)
    if page_info.get("hasNextPage"):
        cursor = page_info.get("endCursor")
        time.sleep(0.3)
    else:
        break

print(f"\nTotal CRM contacts: {len(all_people)}\n", flush=True)

# === 3. Build lookup indexes ===

# Company ID -> phone (from contacts)
company_phones = {}
for p in all_people:
    cid = p.get("companyId", "")
    phone = p.get("phones", {}).get("primaryPhoneNumber", "") if isinstance(p.get("phones"), dict) else ""
    if cid and phone:
        # Normalize phone: remove spaces, dashes, etc.
        clean = re.sub(r'[\s\-\(\)]', '', phone)
        company_phones[cid] = clean

# Build company lookup sets
crm_by_domain = {}   # clean_domain -> [company_ids]
crm_by_phone = {}     # clean_phone -> [company_ids]
crm_companies = all_companies

for c in crm_companies:
    cid = c.get("id", "")
    # Domain
    domain_obj = c.get("domainName", {})
    domain = domain_obj.get("primaryLinkUrl", "") if isinstance(domain_obj, dict) else ""
    if domain:
        clean_d = re.sub(r'^https?://', '', domain.lower())
        clean_d = re.sub(r'^www\.', '', clean_d)
        clean_d = clean_d.split('/')[0]
        if clean_d not in crm_by_domain:
            crm_by_domain[clean_d] = []
        crm_by_domain[clean_d].append(cid)

    # Phone
    phone = company_phones.get(cid, "")
    if phone:
        if phone not in crm_by_phone:
            crm_by_phone[phone] = []
        crm_by_phone[phone].append(cid)

print(f"Index: {len(crm_by_domain)} unique domains, {len(crm_by_phone)} unique phones\n", flush=True)

# === 4. Identify the 36 newly imported companies ===
# They were created today (2026-07-06) by "Mjeed using [Tariq SDR Agent]"
# We'll match by name since we have the CSV
imported_names = set()
imported_domains = set()
imported_phones = set()

for lead in imported_leads:
    name = lead.get("company_name", "").strip().lower()
    domain = lead.get("domain_name", "").strip().lower()
    phone = lead.get("phone", "").strip()
    if name:
        imported_names.add(name)
    if domain:
        clean_d = re.sub(r'^https?://', '', domain)
        clean_d = re.sub(r'^www\.', '', clean_d)
        clean_d = clean_d.split('/')[0]
        imported_domains.add(clean_d)
    if phone:
        clean_p = re.sub(r'[\s\-\(\)]', '', phone)
        imported_phones.add(clean_p)

# === 5. Cross-language duplicate detection ===
# For each CRM company NOT in our import, check if it matches any imported company
# via domain, phone, or cross-language name similarity

print("="*60, flush=True)
print("CROSS-LANGUAGE DUPLICATE CHECK", flush=True)
print("="*60, flush=True)

# Arabic to English transliteration map (common patterns)
# This helps detect "الرشيد" matching "Al Rashid"
ARABIC_TO_LATIN = {
    'ال': 'al', 'الر': 'alr', 'الس': 'als', 'الع': 'ale',
    'أ': 'a', 'إ': 'i', 'آ': 'a', 'ا': 'a', 'ب': 'b', 'ت': 't',
    'ث': 'th', 'ج': 'j', 'ح': 'h', 'خ': 'kh', 'د': 'd', 'ذ': 'th',
    'ر': 'r', 'ز': 'z', 'س': 's', 'ش': 'sh', 'ص': 's', 'ض': 'd',
    'ط': 't', 'ظ': 'z', 'ع': 'a', 'غ': 'gh', 'ف': 'f', 'ق': 'q',
    'ك': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n', 'ه': 'h', 'و': 'w',
    'ي': 'y', 'ى': 'a', 'ة': 'a', 'ئ': 'y', 'ؤ': 'w',
}

def arabic_to_latin(text):
    """Rough transliteration of Arabic to Latin."""
    result = ""
    i = 0
    while i < len(text):
        matched = False
        # Try 2-char prefixes first
        if i + 1 < len(text):
            two = text[i:i+2]
            if two in ARABIC_TO_LATIN:
                result += ARABIC_TO_LATIN[two]
                i += 2
                matched = True
        if not matched:
            one = text[i]
            if one in ARABIC_TO_LATIN:
                result += ARABIC_TO_LATIN[one]
            elif one.isspace():
                result += ' '
            i += 1
    return result.lower().strip()

def normalize_name(name):
    """Normalize a company name for comparison."""
    if not name:
        return ""
    name = name.lower().strip()
    # Remove common suffixes/prefixes
    for word in ['company', 'co', 'ltd', 'l.l.c', 'llc', 'limited', 'شركة', 'محدودة',
                 'for', 'ال', 'and', 'و', 'السعودية', 'saudi', 'arabia', '-']:
        name = name.replace(word, ' ')
    # Remove punctuation
    name = re.sub(r'[^\w\s]', ' ', name)
    # Collapse spaces
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def name_similarity(name1, name2):
    """Check if two names are similar (cross-language)."""
    if not name1 or not name2:
        return False, ""

    n1 = name1.lower().strip()
    n2 = name2.lower().strip()

    # Direct match
    if n1 == n2:
        return True, "exact name"

    # Normalized match
    nn1 = normalize_name(n1)
    nn2 = normalize_name(n2)
    if nn1 and nn2 and nn1 == nn2:
        return True, "normalized name"

    # Check if one Arabic, one English — try transliteration
    is_ar1 = any('\u0600' <= c <= '\u06FF' for c in n1)
    is_ar2 = any('\u0600' <= c <= '\u06FF' for c in n2)

    if is_ar1 and not is_ar2:
        # Transliterate Arabic to Latin
        trans = arabic_to_latin(n1)
        trans_norm = normalize_name(trans)
        nn2_norm = normalize_name(n2)
        if trans_norm and nn2_norm:
            # Check word overlap
            words1 = set(trans_norm.split())
            words2 = set(nn2_norm.split())
            overlap = words1 & words2
            if len(overlap) >= 2 and len(overlap) / min(len(words1), len(words2)) >= 0.4:
                return True, f"transliteration match ({overlap})"
    elif is_ar2 and not is_ar1:
        trans = arabic_to_latin(n2)
        trans_norm = normalize_name(trans)
        nn1_norm = normalize_name(n1)
        if trans_norm and nn1_norm:
            words1 = set(trans_norm.split())
            words2 = set(nn1_norm.split())
            overlap = words1 & words2
            if len(overlap) >= 2 and len(overlap) / min(len(words1), len(words2)) >= 0.4:
                return True, f"transliteration match ({overlap})"

    return False, ""


# === Run the check ===
duplicates = []
clean_count = 0

for lead in imported_leads:
    lead_name = lead.get("company_name", "").strip()
    lead_domain = lead.get("domain_name", "").strip().lower()
    lead_phone = re.sub(r'[\s\-\(\)]', '', lead.get("phone", "").strip())

    if lead_domain:
        lead_domain = re.sub(r'^https?://', '', lead_domain)
        lead_domain = re.sub(r'^www\.', '', lead_domain)
        lead_domain = lead_domain.split('/')[0]

    found_dup = False
    dup_reasons = []

    for crm_co in crm_companies:
        crm_id = crm_co.get("id", "")
        crm_name = crm_co.get("name", "").strip()
        crm_domain_obj = crm_co.get("domainName", {})
        crm_domain = crm_domain_obj.get("primaryLinkUrl", "") if isinstance(crm_domain_obj, dict) else ""
        if crm_domain:
            crm_domain = re.sub(r'^https?://', '', crm_domain.lower())
            crm_domain = re.sub(r'^www\.', '', crm_domain)
            crm_domain = crm_domain.split('/')[0]

        crm_phone = company_phones.get(crm_id, "")

        # Skip self-match (the imported company itself)
        if lead_name.lower() == crm_name.lower():
            continue

        # 1. Domain match
        if lead_domain and crm_domain and lead_domain == crm_domain:
            dup_reasons.append(f"DOMAIN match: {crm_name} (domain={crm_domain})")
            found_dup = True

        # 2. Phone match
        if lead_phone and crm_phone and lead_phone == crm_phone:
            dup_reasons.append(f"PHONE match: {crm_name} (phone={crm_phone})")
            found_dup = True

        # 3. Cross-language name match
        is_match, reason = name_similarity(lead_name, crm_name)
        if is_match:
            dup_reasons.append(f"NAME match: {crm_name} ({reason})")
            found_dup = True

        # 4. Address overlap (check if addresses share significant words)
        crm_addr = crm_co.get("address", {})
        crm_addr_str = ""
        if isinstance(crm_addr, dict):
            crm_addr_str = (crm_addr.get("addressStreet1", "") + " " + crm_addr.get("addressCity", "")).lower()
        lead_addr = lead.get("address", "").lower()

        if crm_addr_str and lead_addr:
            # Extract street names / district names
            addr_words1 = set(w for w in re.findall(r'\w+', lead_addr) if len(w) > 3)
            addr_words2 = set(w for w in re.findall(r'\w+', crm_addr_str) if len(w) > 3)
            addr_overlap = addr_words1 & addr_words2
            # Need significant overlap AND a name/domain signal
            if len(addr_overlap) >= 5 and found_dup:
                dup_reasons.append(f"  + address overlap ({len(addr_overlap)} words)")

    if found_dup:
        duplicates.append((lead_name, dup_reasons))
    else:
        clean_count += 1

# === Report ===
print(f"\n{'='*60}", flush=True)
print(f"CROSS-LANGUAGE DEDUP RESULTS", flush=True)
print(f"{'='*60}", flush=True)
print(f"  Imported leads checked:  {len(imported_leads)}", flush=True)
print(f"  CRM companies compared:  {len(crm_companies)}", flush=True)
print(f"  CRM contacts (phones):   {len(all_people)}", flush=True)
print(f"  Potential duplicates:    {len(duplicates)}", flush=True)
print(f"  Confirmed unique:        {clean_count}", flush=True)

if duplicates:
    print(f"\n--- POTENTIAL DUPLICATES ---", flush=True)
    for i, (name, reasons) in enumerate(duplicates, 1):
        print(f"\n  {i}. {name}", flush=True)
        for r in reasons:
            print(f"     -> {r}", flush=True)
else:
    print(f"\n  No cross-language duplicates found!", flush=True)
    print(f"  All {clean_count} imported companies are truly unique.", flush=True)

print(f"\nDone.", flush=True)

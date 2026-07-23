import sys, io, re, json, csv, time
import nav_env
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import httpx

env_content = open('C:/Users/aabbo/navaia-forge-sdk/.env').read()
token = re.search(r'TWENTY_TOKEN=(.+)', env_content).group(1).strip()
base_url = nav_env.crm_base()

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}

# GraphQL query with proper cursor pagination
query = """
query GetCompanies($first: Int!, $after: String) {
  companies(first: $first, after: $after) {
    edges {
      node {
        id
        name
        domainName {
          primaryLinkUrl
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
    totalCount
  }
}
"""

# 1. Fetch ALL companies via GraphQL
print("Fetching all companies from CRM via GraphQL...", flush=True)
all_companies = []
cursor = None
page = 0

while True:
    variables = {"first": 100}
    if cursor:
        variables["after"] = cursor

    resp = httpx.post(f"{base_url}/graphql", headers=headers,
                      json={"query": query, "variables": variables}, timeout=60)
    if resp.status_code != 200:
        print(f"Error {resp.status_code}: {resp.text[:300]}", flush=True)
        break

    data = resp.json().get("data", {}).get("companies", {})
    edges = data.get("edges", [])
    page_info = data.get("pageInfo", {})
    total = data.get("totalCount", 0)

    for edge in edges:
        all_companies.append(edge["node"])

    page += 1
    print(f"  Page {page}: {len(edges)} companies (total fetched: {len(all_companies)}/{total})", flush=True)

    if page_info.get("hasNextPage"):
        cursor = page_info.get("endCursor")
        time.sleep(0.3)
    else:
        break

print(f"\nTotal CRM companies fetched: {len(all_companies)}", flush=True)

# Build lookup sets
crm_names = set()
crm_domains = set()

for c in all_companies:
    name = c.get("name", "").strip()
    domain_obj = c.get("domainName", {})
    domain = domain_obj.get("primaryLinkUrl", "").strip() if isinstance(domain_obj, dict) else ""
    if name:
        crm_names.add(name.lower())
    if domain:
        clean_domain = re.sub(r'^https?://', '', domain.lower())
        clean_domain = re.sub(r'^www\.', '', clean_domain)
        clean_domain = clean_domain.split('/')[0]
        crm_domains.add(clean_domain)

print(f"  Unique names: {len(crm_names)}", flush=True)
print(f"  Unique domains: {len(crm_domains)}", flush=True)

# 2. Load leads from CSV
csv_path = 'C:/Users/aabbo/navaia-forge-sdk/leads_to_import.csv'
print(f"\nLoading leads from {csv_path}...", flush=True)
leads = []
with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        leads.append(row)

print(f"Total leads in CSV: {len(leads)}", flush=True)

# 3. Check for duplicates
duplicates = []
clean_leads = []

for lead in leads:
    name = lead.get("company_name", "").strip()
    domain = lead.get("domain_name", "").strip()

    name_match = name and name.lower() in crm_names
    domain_match = False
    if domain:
        clean_d = domain.lower()
        clean_d = re.sub(r'^https?://', '', clean_d)
        clean_d = re.sub(r'^www\.', '', clean_d)
        clean_d = clean_d.split('/')[0]
        if clean_d in crm_domains:
            domain_match = True

    if name_match or domain_match:
        reason = []
        if name_match:
            reason.append("name")
        if domain_match:
            reason.append("domain")
        duplicates.append((name, domain, ", ".join(reason)))
    else:
        clean_leads.append(lead)

# 4. Report
print(f"\n{'='*60}", flush=True)
print(f"DEDUP RESULTS", flush=True)
print(f"{'='*60}", flush=True)
print(f"  Total leads checked:  {len(leads)}", flush=True)
print(f"  Duplicates (in CRM): {len(duplicates)}", flush=True)
print(f"  Clean (new) leads:    {len(clean_leads)}", flush=True)

if duplicates:
    print(f"\n--- DUPLICATES (already in CRM) ---", flush=True)
    for i, (name, domain, reason) in enumerate(duplicates, 1):
        print(f"  {i}. {name} | domain={domain} | {reason}", flush=True)

# 5. Write clean leads
if clean_leads:
    out_path = 'C:/Users/aabbo/navaia-forge-sdk/leads_clean.csv'
    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=leads[0].keys())
        writer.writeheader()
        writer.writerows(clean_leads)
    print(f"\nClean leads written to: {out_path}", flush=True)
    print(f"  {len(clean_leads)} leads ready for import", flush=True)
else:
    print("\nAll leads already exist in CRM — nothing to import.", flush=True)

print("\nDone.", flush=True)

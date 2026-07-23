import sys, io, re, json
import nav_env
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os

import httpx

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
token = nav_env.env("TWENTY_TOKEN")
if not token:
    raise SystemExit("TWENTY_TOKEN not found in environment or .env")
base_url = nav_env.crm_base()

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}

# Get ALL people (paginate)
print("=== EXISTING PEOPLE IN CRM ===")
all_people = []
cursor = None
while True:
    params = {"limit": 100}
    if cursor:
        params["after"] = cursor
    resp = httpx.get(f"{base_url}/rest/people", headers=headers, params=params, timeout=30)
    if resp.status_code != 200:
        print(f"Error {resp.status_code}: {resp.text[:300]}")
        break
    data = resp.json()
    people = data.get("data", {}).get("people", [])
    all_people.extend(people)
    page_info = data.get("pageInfo", {})
    cursor = page_info.get("endCursor") if page_info.get("hasNextPage") else None
    if not cursor:
        break

print(f"Total people: {len(all_people)}")
existing_emails = set()
existing_names = set()
for p in all_people:
    name = p.get("name", {})
    first = name.get("firstName", "") if isinstance(name, dict) else ""
    last = name.get("lastName", "") if isinstance(name, dict) else ""
    full = f"{first} {last}".strip()
    email = p.get("emails", {}).get("primaryEmail", "") if isinstance(p.get("emails"), dict) else ""
    phone = p.get("phones", {}).get("primaryPhoneNumber", "") if isinstance(p.get("phones"), dict) else ""
    sector = p.get("sector", "")
    job = p.get("jobTitle", "")
    lead_source = p.get("leadSource", "")
    print(f"  - {full} | email={email} | phone={phone} | sector={sector} | job={job} | source={lead_source}")
    if email:
        existing_emails.add(email.lower())
    if full:
        existing_names.add(full.lower())

# Get ALL companies
print("\n=== EXISTING COMPANIES IN CRM ===")
all_companies = []
cursor = None
while True:
    params = {"limit": 100}
    if cursor:
        params["after"] = cursor
    resp = httpx.get(f"{base_url}/rest/companies", headers=headers, params=params, timeout=30)
    if resp.status_code != 200:
        print(f"Error {resp.status_code}: {resp.text[:300]}")
        break
    data = resp.json()
    companies = data.get("data", {}).get("companies", [])
    all_companies.extend(companies)
    page_info = data.get("pageInfo", {})
    cursor = page_info.get("endCursor") if page_info.get("hasNextPage") else None
    if not cursor:
        break

print(f"Total companies: {len(all_companies)}")
existing_domains = set()
existing_company_names = set()
for c in all_companies:
    name = c.get("name", "")
    domain_obj = c.get("domainName", {})
    domain = domain_obj.get("primaryLinkUrl", "") if isinstance(domain_obj, dict) else ""
    sector = c.get("sector", "")
    print(f"  - {name} | domain={domain} | sector={sector}")
    if name:
        existing_company_names.add(name.lower())
    if domain:
        existing_domains.add(domain.lower())

# Save existing data for the agent task
existing = {
    "emails": sorted(list(existing_emails)),
    "names": sorted(list(existing_names)),
    "company_names": sorted(list(existing_company_names)),
    "domains": sorted(list(existing_domains)),
}
_out = os.path.join(_ROOT, "scripts", "existing_crm_data.json")
with open(_out, "w", encoding="utf-8") as f:
    json.dump(existing, f, indent=2, ensure_ascii=False)
print(f"\nSaved existing CRM data to {_out}")
print(f"  {len(existing_emails)} emails, {len(existing_names)} names, {len(existing_company_names)} companies, {len(existing_domains)} domains")

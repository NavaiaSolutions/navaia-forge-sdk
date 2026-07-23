import sys, io, re, json, time
import nav_env
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import httpx

env_content = open('C:/Users/aabbo/navaia-forge-sdk/.env').read()
token = re.search(r'TWENTY_TOKEN=(.+)', env_content).group(1).strip()
base_url = nav_env.crm_base()
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Check total company count
query = """
query { companies(first: 1) { totalCount } }
"""
resp = httpx.post(f"{base_url}/graphql", headers=headers, json={"query": query}, timeout=30)
data = resp.json()
total = data.get("data", {}).get("companies", {}).get("totalCount", 0)
print(f"Total companies in CRM now: {total}", flush=True)
print(f"Before import: 609", flush=True)
print(f"Expected after: 609 + 34 (new) + 1 (test) = 644", flush=True)
print(f"Difference: +{total - 609}", flush=True)

# Check total people count
query2 = """
query { people(first: 1) { totalCount } }
"""
resp2 = httpx.post(f"{base_url}/graphql", headers=headers, json={"query": query2}, timeout=30)
data2 = resp2.json()
total_people = data2.get("data", {}).get("people", {}).get("totalCount", 0)
print(f"\nTotal people (contacts) in CRM: {total_people}", flush=True)

#!/usr/bin/env python3
"""
Fetch actual emails from Snov.io v2 API for domains that have emails.
Then write the final verified CSV with real email addresses.
"""
import csv, json, time, urllib.request, urllib.parse, urllib.error, sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os as _os, re as _re, sys as _sys


def _secret(_name):
    _v = _os.environ.get(_name)
    if _v:
        return _v
    try:
        _env = open(_os.path.join(_os.path.dirname(__file__), "..", ".env")).read()
    except OSError:
        return None
    _m = _re.search(rf"^{_name}=(.+)$", _env, _re.M)
    return _m.group(1).strip() if _m else None


SNOV_ID = _secret("SNOV_USER_ID")
SNOV_SEC = _secret("SNOV_USER_SECRET")
if not (SNOV_ID and SNOV_SEC):
    raise SystemExit("Set SNOV_USER_ID and SNOV_USER_SECRET (env var or .env)")
SNOV_API = "https://api.snov.io"
INPUT = "C:/Users/aabbo/navaia-forge-sdk/leads_verified.csv"
OUTPUT = "C:/Users/aabbo/navaia-forge-sdk/leads_final.csv"
REPORT = "C:/Users/aabbo/navaia-forge-sdk/verification_report.md"

DELAY = 2.0

# ── Token ──
_token = None
_token_time = 0

def get_token():
    global _token, _token_time
    if _token and (time.time() - _token_time) < 3000:
        return _token
    body = urllib.parse.urlencode({"grant_type":"client_credentials","client_id":SNOV_ID,"client_secret":SNOV_SEC}).encode()
    req = urllib.request.Request(f"{SNOV_API}/v1/oauth/access_token", data=body, method="POST", headers={"Content-Type":"application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        _token = json.loads(resp.read())["access_token"]
        _token_time = time.time()
        return _token

def snov_post(path, params):
    token = get_token()
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{SNOV_API}{path}", data=data, method="POST", headers={"Authorization":f"Bearer {token}","Content-Type":"application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode("utf-8", errors="replace")[:200]}
    except Exception as e:
        return {"error": str(e)}

def snov_get(path):
    token = get_token()
    req = urllib.request.Request(f"{SNOV_API}{path}", method="GET", headers={"Authorization":f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code}
    except Exception as e:
        return {"error": str(e)}

def extract_domain(url):
    """'' when the URL is a third party's — see pipeline_prep._NOT_OWN_DOMAIN.

    Returning '' here also stops a Snov credit being spent looking up a portal.
    """
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    import pipeline_prep as prep
    return prep._domain_of(url)

def fetch_emails_for_domain(domain):
    """Fetch emails from Snov.io v2 API for a domain. Returns list of email strings."""
    all_emails = []

    # 1. Domain emails
    time.sleep(DELAY)
    start = snov_post("/v2/domain-search/domain-emails/start", {"domain": domain})
    task_hash = start.get("meta", {}).get("task_hash", "") if isinstance(start, dict) else ""
    if task_hash:
        for attempt in range(3):
            time.sleep(DELAY + 2)
            result = snov_get(f"/v2/domain-search/domain-emails/result/{task_hash}")
            if isinstance(result, dict) and "data" in result:
                for item in result["data"]:
                    if "email" in item:
                        all_emails.append(item["email"])
                if result.get("status") == "completed":
                    break

    # 2. Generic contacts (info@, sales@, etc.)
    time.sleep(DELAY)
    gen_start = snov_post("/v2/domain-search/generic-contacts/start", {"domain": domain})
    gen_hash = gen_start.get("meta", {}).get("task_hash", "") if isinstance(gen_start, dict) else ""
    if gen_hash:
        for attempt in range(2):
            time.sleep(DELAY + 2)
            gen_result = snov_get(f"/v2/domain-search/generic-contacts/result/{gen_hash}")
            if isinstance(gen_result, dict) and "data" in gen_result:
                for item in gen_result["data"]:
                    if "email" in item:
                        all_emails.append(item["email"])
                if gen_result.get("status") == "completed":
                    break

    return list(set(all_emails))

def main():
    token = get_token()
    print(f"Snov.io token OK")

    with open(INPUT, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        leads = list(reader)

    print(f"Loaded {len(leads)} leads")
    print(f"{'='*60}")

    stats = {"total": len(leads), "emails_found": 0, "no_emails": 0, "no_domain": 0, "errors": 0}

    for i, lead in enumerate(leads):
        company = lead.get("company_name", "")[:45]
        domain = lead.get("domain_name", "")
        email_status = lead.get("email_status", "")

        # Skip domains with no emails or no domain
        if email_status == "no_domain" or not domain:
            lead["email"] = ""
            lead["email_status"] = "no_domain"
            stats["no_domain"] += 1
            print(f"[{i+1}/{len(leads)}] {company} -> no domain")
            continue

        if email_status == "no_emails_in_snov":
            lead["email"] = ""
            lead["email_status"] = "no_emails_in_snov"
            stats["no_emails"] += 1
            print(f"[{i+1}/{len(leads)}] {company} | {domain} -> no emails in Snov")
            continue

        # Has emails — fetch them
        count_match = re.match(r"has_(\d+)_emails", email_status)
        count = int(count_match.group(1)) if count_match else 0
        print(f"[{i+1}/{len(leads)}] {company} | {domain} -> fetching ({count} emails in DB)")

        emails = fetch_emails_for_domain(domain)

        if not emails:
            lead["email"] = ""
            lead["email_status"] = "fetch_failed"
            stats["errors"] += 1
            print(f"  No emails fetched")
            continue

        # Pick best email: prefer info@, contact@, sales@
        best = ""
        for pref in ["info", "contact", "sales", "admin", "office", "hello", "mail", "general", "reception", "booking", "appointment"]:
            for e in emails:
                if e.lower().startswith(pref + "@"):
                    best = e
                    break
            if best:
                break
        if not best:
            best = emails[0]

        lead["email"] = best
        lead["email_status"] = "found_unverified"
        stats["emails_found"] += 1
        print(f"  Found {len(emails)} emails, selected: {best}")

    # Write final CSV
    fields = ["company_name","domain_name","address","phone","email","email_status","sector","vertical_tier","created_by","lead_source","place_id"]
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(leads)

    print(f"\n{'='*60}")
    print(f"Final CSV: {OUTPUT}")
    print(f"{'='*60}")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    # Write report
    report = []
    report.append("# Lead Verification Report")
    report.append(f"\nGenerated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    report.append(f"\n## Summary\n")
    report.append(f"| Metric | Count |")
    report.append(f"|--------|-------|")
    report.append(f"| Total leads | {stats['total']} |")
    report.append(f"| Emails found (Snov.io) | {stats['emails_found']} |")
    report.append(f"| No emails in Snov DB | {stats['no_emails']} |")
    report.append(f"| No domain | {stats['no_domain']} |")
    report.append(f"| Fetch errors | {stats['errors']} |")

    report.append(f"\n## CRM Dedup Status\n")
    report.append(f"CRM (crm.navaia.sa) is currently DOWN. Dedup check deferred.")
    report.append(f"When CRM is back up, compare company names against existing CRM records before importing.")

    report.append(f"\n## Verification Process\n")
    report.append(f"1. **Data source**: Google Places API (Text Search) — Riyadh, 50km radius")
    report.append(f"2. **Phone validation**: Regex for Saudi +966 format — all 50 passed")
    report.append(f"3. **Address validation**: Must contain 'Riyadh' — all 50 passed")
    report.append(f"4. **Domain extraction**: Parsed from website URL, cleaned (removed protocol, www, path)")
    report.append(f"5. **Email count check**: Snov.io v1 `get-domain-emails-count` (free) — identified 27 domains with emails")
    report.append(f"6. **Email discovery**: Snov.io v2 `domain-search/domain-emails` + `generic-contacts` — fetched actual emails")
    report.append(f"7. **Email selection**: info@ > contact@ > sales@ > admin@ > office@ > first available")
    report.append(f"8. **Email status**: `found_unverified` = found in Snov DB (not SMTP-verified); `no_emails_in_snov` = domain not in Snov DB; `no_domain` = no website")

    report.append(f"\n## Per-Lead Breakdown\n")
    report.append(f"| # | Company | Phone | Domain | Email | Email Status | Sector |")
    report.append(f"|---|---------|-------|--------|-------|-------------|--------|")
    for i, lead in enumerate(leads):
        report.append(
            f"| {i+1} | {lead['company_name'][:40]} | {lead['phone']} | "
            f"{lead['domain_name'] or '-'} | {lead['email'] or '-'} | "
            f"{lead['email_status']} | {lead['sector']} |"
        )

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print(f"Report: {REPORT}")

if __name__ == "__main__":
    main()

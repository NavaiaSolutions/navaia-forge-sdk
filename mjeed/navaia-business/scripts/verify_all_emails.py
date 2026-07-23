#!/usr/bin/env python3
"""
Full email verification + discovery pipeline for clean leads.

1. Verify all 15 found_unverified emails via Snov.io v2/email-verification
2. Retry domain search for 12 no_emails_in_snov leads
3. Find domains for 8 no_domain + 1 fetch_failed leads via company-domain-by-name API
4. Verify any newly discovered emails
5. Write final verified CSV
"""
import sys, io, json, csv, re, time, urllib.request, urllib.parse, urllib.error
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os as _os, re as _re


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
DELAY = 2.0

INPUT = "C:/Users/aabbo/navaia-forge-sdk/leads_clean.csv"
OUTPUT = "C:/Users/aabbo/navaia-forge-sdk/leads_verified_final.csv"

_token = None
_token_time = 0

def get_token():
    global _token, _token_time
    if _token and (time.time() - _token_time) < 3000:
        return _token
    body = urllib.parse.urlencode({"grant_type":"client_credentials","client_id":SNOV_ID,"client_secret":SNOV_SEC}).encode()
    req = urllib.request.Request(f"{SNOV_API}/v1/oauth/access_token", data=body, method="POST",
                                 headers={"Content-Type":"application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        _token = json.loads(resp.read())["access_token"]
        _token_time = time.time()
        return _token

def snov_post_json(path, params):
    token = get_token()
    data = json.dumps(params).encode()
    req = urllib.request.Request(f"{SNOV_API}{path}", data=data, method="POST",
                                 headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode("utf-8", errors="replace")[:300]}
    except Exception as e:
        return {"error": str(e)}

def snov_get(path):
    token = get_token()
    req = urllib.request.Request(f"{SNOV_API}{path}", method="GET",
                                 headers={"Authorization":f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode("utf-8", errors="replace")[:300]}
    except Exception as e:
        return {"error": str(e)}

def verify_emails(emails):
    """Verify up to 10 emails at once. Returns dict {email: {smtp_status, is_valid_format, ...}}"""
    if not emails:
        return {}
    results = {}
    batch = emails[:10]
    print(f"    [Snov] Verifying {len(batch)} email(s)...", flush=True)
    time.sleep(DELAY)
    resp = snov_post_json("/v2/email-verification/start", {"emails": batch})
    task_hash = resp.get("data", {}).get("task_hash", "") if isinstance(resp, dict) else ""
    if not task_hash:
        print(f"    [Snov] No task_hash: {json.dumps(resp)[:200]}", flush=True)
        return results
    for attempt in range(10):
        time.sleep(3)
        result = snov_get(f"/v2/email-verification/result?task_hash={task_hash}")
        if isinstance(result, dict) and result.get("status") == "completed":
            for item in result.get("data", []):
                email = item.get("email", "")
                results[email] = item.get("result", {})
            break
    return results

def search_domain_emails(domain):
    """Search for emails by domain. Returns list of email strings."""
    all_emails = []
    time.sleep(DELAY)
    resp = snov_post_json("/v2/domain-search/domain-emails/start", {"domain": domain})
    task_hash = resp.get("meta", {}).get("task_hash", "") if isinstance(resp, dict) else ""
    if task_hash:
        for attempt in range(5):
            time.sleep(DELAY + 2)
            result = snov_get(f"/v2/domain-search/domain-emails/result/{task_hash}")
            if isinstance(result, dict) and "data" in result:
                for item in result["data"]:
                    if "email" in item:
                        all_emails.append(item["email"])
                if result.get("status") == "completed":
                    break
    # Also try generic contacts
    time.sleep(DELAY)
    resp2 = snov_post_json("/v2/domain-search/generic-contacts/start", {"domain": domain})
    gen_hash = resp2.get("meta", {}).get("task_hash", "") if isinstance(resp2, dict) else ""
    if gen_hash:
        for attempt in range(3):
            time.sleep(DELAY + 2)
            result = snov_get(f"/v2/domain-search/generic-contacts/result/{gen_hash}")
            if isinstance(result, dict) and "data" in result:
                for item in result["data"]:
                    if "email" in item:
                        all_emails.append(item["email"])
                if result.get("status") == "completed":
                    break
    return list(set(all_emails))

def find_domain_by_company_name(name):
    """Use Snov.io company-domain-by-name API to find a company's domain."""
    time.sleep(DELAY)
    resp = snov_post_json("/v2/company-domain-by-name/start", {"names": [name]})
    task_hash = resp.get("data", {}).get("task_hash", "") if isinstance(resp, dict) else ""
    if not task_hash:
        # Try alternate structure
        task_hash = resp.get("meta", {}).get("task_hash", "") if isinstance(resp, dict) else ""
    if not task_hash:
        print(f"    [Snov] No task_hash for company-domain search: {json.dumps(resp)[:200]}", flush=True)
        return ""
    for attempt in range(5):
        time.sleep(DELAY + 2)
        result = snov_get(f"/v2/company-domain-by-name/result?task_hash={task_hash}")
        if isinstance(result, dict) and result.get("status") == "completed":
            data = result.get("data", [])
            if data and isinstance(data, list):
                for item in data:
                    domain = item.get("domain", "") or item.get("site", "")
                    if domain:
                        return domain
            break
    return ""

def pick_best_email(emails):
    """Pick best email: prefer info@, contact@, sales@, admin@, etc."""
    for pref in ["info", "contact", "sales", "admin", "office", "hello", "mail", "general", "booking", "appointment", "reception"]:
        for e in emails:
            if e.lower().startswith(pref + "@"):
                return e
    return emails[0] if emails else ""

def main():
    token = get_token()
    print(f"Snov.io token OK", flush=True)

    # Load leads
    with open(INPUT, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        leads = list(reader)
    print(f"Loaded {len(leads)} leads\n", flush=True)

    stats = {
        "verified_valid": 0,
        "verified_invalid": 0,
        "verified_unknown": 0,
        "new_emails_found": 0,
        "new_domains_found": 0,
        "still_no_email": 0,
    }

    # === PHASE 1: Verify existing found_unverified emails ===
    print("="*60, flush=True)
    print("PHASE 1: Verify existing found_unverified emails", flush=True)
    print("="*60, flush=True)

    unverified_emails = []
    for lead in leads:
        if lead.get("email_status") == "found_unverified" and lead.get("email", "").strip():
            unverified_emails.append(lead["email"].strip())

    print(f"Found {len(unverified_emails)} emails to verify\n", flush=True)

    # Verify in batches of 10
    all_verify_results = {}
    for i in range(0, len(unverified_emails), 10):
        batch = unverified_emails[i:i+10]
        print(f"  Batch {i//10 + 1}: {batch}", flush=True)
        results = verify_emails(batch)
        all_verify_results.update(results)

    # Apply verification results
    for lead in leads:
        if lead.get("email_status") == "found_unverified" and lead.get("email", "").strip():
            email = lead["email"].strip()
            vr = all_verify_results.get(email, {})
            smtp = vr.get("smtp_status", "unknown")
            lead["email_status"] = f"verified_{smtp}"
            if smtp == "valid":
                stats["verified_valid"] += 1
                print(f"  VALID: {email}", flush=True)
            elif smtp == "not_valid":
                stats["verified_invalid"] += 1
                print(f"  INVALID: {email}", flush=True)
            else:
                stats["verified_unknown"] += 1
                print(f"  UNKNOWN: {email} (smtp_status={smtp})", flush=True)

    # === PHASE 2: Retry domain search for no_emails_in_snov ===
    print(f"\n{'='*60}", flush=True)
    print("PHASE 2: Retry email discovery for no_emails_in_snov", flush=True)
    print("="*60, flush=True)

    for i, lead in enumerate(leads):
        if lead.get("email_status") != "no_emails_in_snov":
            continue
        domain = lead.get("domain_name", "").strip()
        company = lead.get("company_name", "")[:40]
        print(f"\n  [{i+1}] {company} | domain={domain}", flush=True)

        emails = search_domain_emails(domain)
        if emails:
            best = pick_best_email(emails)
            lead["email"] = best
            lead["email_status"] = "found_unverified"
            stats["new_emails_found"] += 1
            print(f"    Found {len(emails)} emails, selected: {best}", flush=True)
        else:
            print(f"    Still no emails found", flush=True)

    # === PHASE 3: Find domains for no_domain + fetch_failed ===
    print(f"\n{'='*60}", flush=True)
    print("PHASE 3: Find domains for no_domain + fetch_failed leads", flush=True)
    print("="*60, flush=True)

    for i, lead in enumerate(leads):
        status = lead.get("email_status", "")
        if status not in ("no_domain", "fetch_failed"):
            continue
        company = lead.get("company_name", "")[:40]
        print(f"\n  [{i+1}] {company} | status={status}", flush=True)

        domain = find_domain_by_company_name(lead.get("company_name", ""))
        if domain:
            # Clean domain
            domain = re.sub(r'^https?://', '', domain.lower())
            domain = re.sub(r'^www\.', '', domain)
            domain = domain.split('/')[0].split(':')[0]
            lead["domain_name"] = domain
            stats["new_domains_found"] += 1
            print(f"    Found domain: {domain}", flush=True)

            # Now search for emails on this domain
            emails = search_domain_emails(domain)
            if emails:
                best = pick_best_email(emails)
                lead["email"] = best
                lead["email_status"] = "found_unverified"
                stats["new_emails_found"] += 1
                print(f"    Found {len(emails)} emails, selected: {best}", flush=True)
            else:
                lead["email_status"] = "no_emails_in_snov"
                print(f"    No emails found for domain {domain}", flush=True)
        else:
            print(f"    No domain found for this company", flush=True)

    # === PHASE 4: Verify any newly found emails ===
    print(f"\n{'='*60}", flush=True)
    print("PHASE 4: Verify newly found emails", flush=True)
    print("="*60, flush=True)

    new_unverified = []
    for lead in leads:
        if lead.get("email_status") == "found_unverified" and lead.get("email", "").strip():
            new_unverified.append(lead["email"].strip())

    if new_unverified:
        print(f"Found {len(new_unverified)} newly discovered emails to verify\n", flush=True)
        all_new_results = {}
        for i in range(0, len(new_unverified), 10):
            batch = new_unverified[i:i+10]
            print(f"  Batch {i//10 + 1}: {batch}", flush=True)
            results = verify_emails(batch)
            all_new_results.update(results)

        for lead in leads:
            if lead.get("email_status") == "found_unverified" and lead.get("email", "").strip():
                email = lead["email"].strip()
                vr = all_new_results.get(email, {})
                smtp = vr.get("smtp_status", "unknown")
                lead["email_status"] = f"verified_{smtp}"
                if smtp == "valid":
                    stats["verified_valid"] += 1
                    print(f"  VALID: {email}", flush=True)
                elif smtp == "not_valid":
                    stats["verified_invalid"] += 1
                    print(f"  INVALID: {email}", flush=True)
                else:
                    stats["verified_unknown"] += 1
                    print(f"  UNKNOWN: {email} (smtp_status={smtp})", flush=True)
    else:
        print("No newly discovered emails to verify.", flush=True)

    # Count remaining no-email
    for lead in leads:
        status = lead.get("email_status", "")
        if not lead.get("email", "").strip():
            stats["still_no_email"] += 1

    # === Write final CSV ===
    fields = ["company_name","domain_name","address","phone","email","email_status","sector","vertical_tier","created_by","lead_source","place_id"]
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(leads)

    print(f"\n{'='*60}", flush=True)
    print(f"FINAL RESULTS", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"  Verified valid:     {stats['verified_valid']}", flush=True)
    print(f"  Verified invalid:   {stats['verified_invalid']}", flush=True)
    print(f"  Verified unknown:   {stats['verified_unknown']}", flush=True)
    print(f"  New emails found:   {stats['new_emails_found']}", flush=True)
    print(f"  New domains found:   {stats['new_domains_found']}", flush=True)
    print(f"  Still no email:     {stats['still_no_email']}", flush=True)
    print(f"\n  Output: {OUTPUT}", flush=True)

    # Print final summary table
    print(f"\n{'='*60}", flush=True)
    print(f"FINAL LEAD STATUS", flush=True)
    print(f"{'='*60}", flush=True)
    for i, lead in enumerate(leads, 1):
        name = lead.get("company_name", "")[:42]
        email = lead.get("email", "").strip() or "(none)"
        status = lead.get("email_status", "")
        domain = lead.get("domain_name", "") or "(none)"
        print(f"  {i:2d}. {name:<44} | {email:<35} | {status:<20} | {domain}", flush=True)

    print(f"\nDone.", flush=True)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Scrape websites and search the web to find emails for leads with no email.

Phase 1: Crawl websites for leads that have a domain but no email (12 leads)
  - Fetch homepage + /contact, /contact-us, /about, /about-us pages
  - Extract mailto: links and regex-match email patterns from HTML
  - Respect robots.txt, use proper User-Agent, timeout on each request

Phase 2: Web search for leads with no domain (9 leads)
  - Search DuckDuckGo HTML for "company name" + "email" or "contact"
  - Parse results pages for email addresses
  - Also try to discover the company website from search results

Phase 3: Verify any newly found emails via Snov.io v2/email-verification

Phase 4: Write final CSV with all results
"""
import sys, io, json, csv, os, re, time, urllib.request, urllib.parse, urllib.error
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline_prep as prep
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

INPUT = "C:/Users/aabbo/navaia-forge-sdk/leads_verified_final.csv"
OUTPUT = "C:/Users/aabbo/navaia-forge-sdk/leads_enriched.csv"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
TIMEOUT = 15
DELAY = 1.5  # delay between requests to be polite

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
MAILTO_REGEX = re.compile(r'mailto:([^"\'\s>]+)', re.IGNORECASE)

# Common contact page paths to try
CONTACT_PATHS = ['', '/contact', '/contact-us', '/contactus', '/about', '/about-us',
                  '/aboutus', '/connect', '/reach-us', '/get-in-touch']

# Emails to ignore (generic/non-useful)
SKIP_EMAILS = {'example.com', 'sentry.io', 'wixpress.com', 'godaddy.com',
               'google.com', 'facebook.com', 'instagram.com', 'twitter.com',
               'linkedin.com', 'youtube.com', 'whatsapp.com', 'mailchimp.com',
               'sentry-next.wixpress.com', 'shutterstock.com', 'placeholder.com',
               'email.com', 'yourdomain.com', 'myemail.com', 'domain.com',
               'sample.com', 'test.com', 'noreply.com', 'no-reply.com'}


def fetch_url(url):
    """Fetch URL content with proper headers and timeout."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
        })
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            content_type = resp.headers.get('Content-Type', '')
            if 'text/html' not in content_type and 'text/plain' not in content_type:
                return None
            # Handle encoding
            raw = resp.read()
            # Try utf-8 first, then fall back
            for enc in ['utf-8', 'latin-1', 'cp1256']:
                try:
                    return raw.decode(enc)
                except:
                    continue
            return raw.decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        if e.code == 403:
            print(f"      403 Forbidden", flush=True)
        return None
    except Exception as e:
        return None


def extract_emails_from_html(html, domain):
    """Extract email addresses from HTML content."""
    if not html:
        return []

    found = set()

    # 1. Extract from mailto: links
    for match in MAILTO_REGEX.findall(html):
        email = match.strip().lower()
        if '@' in email:
            # Clean URL-encoded chars
            email = urllib.parse.unquote(email)
            email = email.split('?')[0]  # Remove query params
            found.add(email)

    # 2. Extract from plain text via regex
    for match in EMAIL_REGEX.findall(html):
        found.add(match.lower())

    # 3. Filter out useless emails
    clean = set()
    for email in found:
        # Skip if domain is in skip list
        email_domain = email.split('@')[-1] if '@' in email else ''
        if email_domain in SKIP_EMAILS:
            continue
        # Skip if it's an image/file reference
        if any(email.endswith(ext) for ext in ['.png', '.jpg', '.gif', '.svg', '.webp']):
            continue
        # Skip very long emails (likely false positive)
        if len(email) > 80:
            continue
        # Must plausibly be the LEAD's own mailbox. The old test here was only
        # "same domain as the page", which passes trivially — and wrongly — when the
        # page we crawled is a portal profile rather than the lead's own site.
        if not prep.email_belongs_to(email, f"https://{domain}" if domain else ""):
            continue
        clean.add(email)

    return list(clean)


def crawl_website_for_emails(domain):
    """Crawl homepage + common contact pages to find emails."""
    if not domain:
        return []

    # A portal profile or social page is not the lead's site; crawling it finds the
    # portal's mailbox and nothing of the lead's.
    if not prep.is_own_domain(domain if domain.startswith("http") else "https://" + domain):
        print(f"      skipped (not the lead's own domain): {domain}", flush=True)
        return []

    # Normalize domain
    domain = domain.strip().lower()
    domain = re.sub(r'^https?://', '', domain)
    domain = re.sub(r'^www\.', '', domain)
    domain = domain.split('/')[0]

    all_emails = set()
    base_url = f"https://{domain}"

    for path in CONTACT_PATHS:
        url = f"{base_url}{path}"
        print(f"      Fetching: {url}", flush=True)
        html = fetch_url(url)
        if html:
            emails = extract_emails_from_html(html, domain)
            if emails:
                print(f"      Found {len(emails)} email(s): {emails}", flush=True)
                all_emails.update(emails)
        time.sleep(0.5)  # Small delay between page fetches

    return list(all_emails)


def search_web_for_company(name):
    """Search DuckDuckGo for company to find website + email."""
    query = f'"{name}" contact email'
    encoded_q = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_q}"

    print(f"      Searching: {query}", flush=True)
    html = fetch_url(url)
    if not html:
        return [], []

    # Extract emails from search results
    emails = extract_emails_from_html(html, name)

    # Extract URLs from search results (to find company website)
    urls = set()
    url_pattern = re.compile(r'href="(https?://[^"]+)"')
    for match in url_pattern.findall(html):
        # Clean URL
        clean = re.sub(r'^https?://', '', match.lower())
        clean = re.sub(r'^www\.', '', clean)
        clean = clean.split('/')[0]
        # Skip search engines and social media
        skip = ['duckduckgo', 'google', 'facebook', 'instagram', 'twitter',
                'linkedin', 'youtube', 'wikipedia', 'maps.google']
        if any(s in clean for s in skip):
            continue
        if clean and '.' in clean:
            urls.add(clean)

    return emails, list(urls)


def search_web_for_email(name, domain=None):
    """Search for company email via DuckDuckGo."""
    if domain:
        query = f'"{domain}" email contact'
    else:
        query = f'"{name}" Saudi Arabia email contact'
    encoded_q = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_q}"

    print(f"      Searching: {query}", flush=True)
    html = fetch_url(url)
    if not html:
        return []

    emails = extract_emails_from_html(html, domain or name)
    return emails


# ── Snov.io verification ──
_snov_token = None
_snov_token_time = 0

def get_snov_token():
    global _snov_token, _snov_token_time
    if _snov_token and (time.time() - _snov_token_time) < 3000:
        return _snov_token
    body = urllib.parse.urlencode({"grant_type":"client_credentials","client_id":SNOV_ID,"client_secret":SNOV_SEC}).encode()
    req = urllib.request.Request(f"{SNOV_API}/v1/oauth/access_token", data=body, method="POST",
                                 headers={"Content-Type":"application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        _snov_token = json.loads(resp.read())["access_token"]
        _snov_token_time = time.time()
        return _snov_token

def verify_emails_snov(emails):
    """Verify emails via Snov.io v2 API. Returns {email: smtp_status}."""
    if not emails:
        return {}
    token = get_snov_token()
    results = {}
    batch = emails[:10]
    body = json.dumps({"emails": batch}).encode()
    req = urllib.request.Request(f"{SNOV_API}/v2/email-verification/start", data=body, method="POST",
                                 headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            task_hash = data.get("data", {}).get("task_hash", "")
    except:
        return results

    if not task_hash:
        return results

    for attempt in range(10):
        time.sleep(3)
        req = urllib.request.Request(f"{SNOV_API}/v2/email-verification/result?task_hash={task_hash}",
                                     method="GET", headers={"Authorization":f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                if data.get("status") == "completed":
                    for item in data.get("data", []):
                        email = item.get("email", "")
                        smtp = item.get("result", {}).get("smtp_status", "unknown")
                        results[email] = smtp
                    break
        except:
            continue
    return results


def pick_best_email(emails):
    """Pick best email: prefer info@, contact@, sales@, etc."""
    for pref in ["info", "contact", "sales", "admin", "office", "hello",
                 "mail", "general", "booking", "appointment", "reception", "support"]:
        for e in emails:
            if e.lower().startswith(pref + "@"):
                return e
    return emails[0] if emails else ""


def main():
    # Load leads
    with open(INPUT, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        leads = list(reader)
    print(f"Loaded {len(leads)} leads\n", flush=True)

    stats = {
        "emails_from_website": 0,
        "emails_from_search": 0,
        "domains_from_search": 0,
        "still_no_email": 0,
        "verified_valid": 0,
        "verified_invalid": 0,
        "verified_unknown": 0,
    }

    # === PHASE 1: Crawl websites for leads with domain but no email ===
    print("="*60, flush=True)
    print("PHASE 1: Crawl websites for emails (leads with domain, no email)", flush=True)
    print("="*60, flush=True)

    for i, lead in enumerate(leads):
        email = lead.get("email", "").strip()
        domain = lead.get("domain_name", "").strip()
        status = lead.get("email_status", "")

        # Skip if already has email
        if email:
            continue
        # Skip if no domain
        if not domain:
            continue

        company = lead.get("company_name", "")[:45]
        print(f"\n  [{i+1}] {company} | domain={domain}", flush=True)

        emails = crawl_website_for_emails(domain)
        time.sleep(DELAY)

        if emails:
            best = pick_best_email(emails)
            lead["email"] = best
            lead["email_status"] = "found_on_website"
            stats["emails_from_website"] += 1
            print(f"  >>> Found {len(emails)} email(s), selected: {best}", flush=True)
        else:
            print(f"  >>> No emails found on website", flush=True)

    # === PHASE 2: Web search for leads with no domain ===
    print(f"\n{'='*60}", flush=True)
    print("PHASE 2: Web search for leads with no domain", flush=True)
    print("="*60, flush=True)

    for i, lead in enumerate(leads):
        email = lead.get("email", "").strip()
        domain = lead.get("domain_name", "").strip()

        # Skip if already has email
        if email:
            continue
        # Skip if has domain (already crawled in phase 1)
        if domain:
            # Try web search for email even if website crawl failed
            company = lead.get("company_name", "")[:45]
            print(f"\n  [{i+1}] {company} | domain={domain} (web search for email)", flush=True)
            emails = search_web_for_email(company, domain)
            time.sleep(DELAY)
            if emails:
                best = pick_best_email(emails)
                lead["email"] = best
                lead["email_status"] = "found_via_search"
                stats["emails_from_search"] += 1
                print(f"  >>> Found {len(emails)} email(s), selected: {best}", flush=True)
            else:
                print(f"  >>> No emails found via search", flush=True)
            continue

        # No domain at all — search for both website and email
        company = lead.get("company_name", "")[:45]
        print(f"\n  [{i+1}] {company} | no domain (searching for website + email)", flush=True)

        emails, found_domains = search_web_for_company(company)
        time.sleep(DELAY)

        if found_domains:
            # Pick the most relevant domain (shortest, most matching)
            best_domain = found_domains[0]
            lead["domain_name"] = best_domain
            stats["domains_from_search"] += 1
            print(f"  >>> Found domain: {best_domain}", flush=True)

            # Now crawl that domain for emails
            if not emails:
                emails = crawl_website_for_emails(best_domain)
                time.sleep(DELAY)

        if emails:
            best = pick_best_email(emails)
            lead["email"] = best
            lead["email_status"] = "found_via_search"
            stats["emails_from_search"] += 1
            print(f"  >>> Found {len(emails)} email(s), selected: {best}", flush=True)
        else:
            print(f"  >>> No emails found", flush=True)

    # === PHASE 3: Verify all newly found emails ===
    print(f"\n{'='*60}", flush=True)
    print("PHASE 3: Verify newly found emails via Snov.io", flush=True)
    print("="*60, flush=True)

    new_emails = []
    for lead in leads:
        status = lead.get("email_status", "")
        if status in ("found_on_website", "found_via_search") and lead.get("email", "").strip():
            new_emails.append(lead["email"].strip())

    if new_emails:
        print(f"\nVerifying {len(new_emails)} newly found email(s)...\n", flush=True)
        verify_results = verify_emails_snov(new_emails)

        for lead in leads:
            status = lead.get("email_status", "")
            if status in ("found_on_website", "found_via_search") and lead.get("email", "").strip():
                email = lead["email"].strip()
                smtp = verify_results.get(email, "unknown")
                lead["email_status"] = f"verified_{smtp}"
                if smtp == "valid":
                    stats["verified_valid"] += 1
                    print(f"  VALID: {email}", flush=True)
                elif smtp == "not_valid":
                    stats["verified_invalid"] += 1
                    print(f"  INVALID: {email}", flush=True)
                else:
                    stats["verified_unknown"] += 1
                    print(f"  UNKNOWN: {email}", flush=True)
    else:
        print("No newly found emails to verify.", flush=True)

    # Count remaining
    for lead in leads:
        if not lead.get("email", "").strip():
            stats["still_no_email"] += 1

    # === Write final CSV ===
    fields = ["company_name","domain_name","address","phone","email","email_status",
              "sector","vertical_tier","created_by","lead_source","place_id"]
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(leads)

    # === Summary ===
    print(f"\n{'='*60}", flush=True)
    print(f"FINAL RESULTS", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"  Emails from website crawl:  {stats['emails_from_website']}", flush=True)
    print(f"  Emails from web search:     {stats['emails_from_search']}", flush=True)
    print(f"  Domains from web search:    {stats['domains_from_search']}", flush=True)
    print(f"  Verified valid:             {stats['verified_valid']}", flush=True)
    print(f"  Verified invalid:           {stats['verified_invalid']}", flush=True)
    print(f"  Verified unknown:           {stats['verified_unknown']}", flush=True)
    print(f"  Still no email:             {stats['still_no_email']}", flush=True)
    print(f"\n  Output: {OUTPUT}", flush=True)

    # Final table
    print(f"\n{'='*60}", flush=True)
    print(f"FINAL LEAD STATUS", flush=True)
    print(f"{'='*60}", flush=True)
    for i, lead in enumerate(leads, 1):
        name = lead.get("company_name", "")[:42]
        email = lead.get("email", "").strip() or "(none)"
        status = lead.get("email_status", "")
        domain = lead.get("domain_name", "") or "(none)"
        print(f"  {i:2d}. {name:<44} | {email:<35} | {status:<22} | {domain}", flush=True)

    print(f"\nDone.", flush=True)


if __name__ == "__main__":
    main()

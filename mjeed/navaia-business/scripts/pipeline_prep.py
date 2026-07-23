#!/usr/bin/env python3
"""
Deterministic prep for pipeline tasks — run automatically by run_pipeline.py /
submit_lead_batch.py so the operator never repeats a step. Everything here is
plain HTTP (no LLM): the flaky parts of the first cloud runs (in-task Snov
enrichment, in-task CRM field fixes, improvised copy) become data prepared
BEFORE the task is submitted.

Provides:
- email_touch1_templates() / wa_templates(): the approved Touch-1 copy per
  vertical, parsed VERBATIM from workforce/04_outreach_templates.md — embedded
  into every task so copy is fill-in-the-tokens, never improvised.
- enrich_leads(leads): Snov v2 domain-search + verify, attaches email/
  email_status to lead dicts (idempotent: skips leads already checked).
- normalize_crm_people(): fills missing Person.sector (from the company) and
  Person.leadStatus="Not Contacted" for Mjeed's records.
- enrich_crm_not_contacted(): Snov emails for Mjeed's Not Contacted people
  whose company has a domain but the person has no email.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import time

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nav_env

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
TEMPLATES_MD = os.path.join(ROOT, "workforce", "04_outreach_templates.md")
SCRAPE_POOL = os.path.join(ROOT, "leads_scraped_compact.json")
CRM_BASE = nav_env.crm_base()
SNOV_API = "https://api.snov.io"


def _phone9(p: str) -> str:
    """Last 9 digits — the only phone form that matches across CRM/scrape/OSM."""
    d = re.sub(r"\D", "", p or "")
    return d[-9:] if len(d) >= 9 else ""


_pain_index: dict[str, str] | None = None


def scrape_pain_index() -> dict[str, str]:
    """{phone9: pain text} from the scrape pool — the lead's OWN review snippets.

    Why this exists: the designed review-enrichment step (enrich_reviews.py) is
    trust-locked to a Google *Places* place_id, and Places is retired — so nothing
    was carrying per-lead pain into the render and every lead silently fell back to
    the general block. The gosom scrape already captures same-listing review text;
    this indexes it by phone so not_contacted_leads() can attach it.

    Trust: phone is matched exactly (last 9 digits), so a hint can only ever reach
    the lead whose listing produced it — same guarantee place_id gave us.
    The raw text still NEVER ships: lina_compose.select() uses it only to PICK a
    pain category, whose own neutral wording is what goes in the message.
    """
    global _pain_index
    if _pain_index is not None:
        return _pain_index
    _pain_index = {}
    try:
        with open(SCRAPE_POOL, encoding="utf-8") as f:
            for lead in json.load(f):
                key = _phone9(lead.get("phone", ""))
                hints = lead.get("pain_hints") or []
                if key and hints:
                    _pain_index[key] = " ".join(hints)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return _pain_index
SNOV_DELAY = 2.0

VERTICAL_BY_NUM = {
    "Vertical 1": "Contracting & Facilities",
    "Vertical 2": "Finance & Debt Collection",
    "Vertical 3": "Private Clinics",
    "Vertical 4": "Real Estate",
    "Vertical 5": "Training Institutes",
}
WA_BY_KEYWORD = {
    "Clinics": "Private Clinics",
    "Contracting": "Contracting & Facilities",
    "Finance": "Finance & Debt Collection",
    "Real Estate": "Real Estate",
    "Training": "Training Institutes",
}


# ── Approved templates (verbatim from 04_outreach_templates.md) ───────────────

def _md() -> str:
    return open(TEMPLATES_MD, encoding="utf-8").read()


def email_touch1_templates() -> dict[str, str]:
    """{CRM sector: verbatim Touch-1 email template (subject line + body)}."""
    text = _md()
    out: dict[str, str] = {}
    for m in re.finditer(r"(?ms)^## (Vertical \d) .*?^### Touch 1 : Day 0\n(.*?)(?=^### )", text):
        sector = VERTICAL_BY_NUM.get(m.group(1))
        if sector:
            out[sector] = m.group(2).strip()
    return out


def wa_templates() -> dict[str, dict[str, str]]:
    """{CRM sector: {"name": meta template name, "body": verbatim approved body}}."""
    text = _md()
    out: dict[str, dict[str, str]] = {}
    for m in re.finditer(
            r"(?ms)^### WhatsApp Touch 1 : (.+?) \(`([a-z0-9_]+)`.*?```\n(.*?)```", text):
        label, name, body = m.group(1).strip(), m.group(2), m.group(3).strip()
        for kw, sector in WA_BY_KEYWORD.items():
            if kw.lower() in label.lower():
                out[sector] = {"name": name, "body": body}
                break
    return out


# ── Snov.io v2 (direct HTTP, same endpoints the docs bless) ───────────────────

_token: str | None = None
_token_ts = 0.0


def _snov_token() -> str:
    global _token, _token_ts
    if _token and time.time() - _token_ts < 3000:
        return _token
    r = httpx.post(f"{SNOV_API}/v1/oauth/access_token", data={
        "grant_type": "client_credentials",
        "client_id": nav_env.env("SNOV_USER_ID"),
        "client_secret": nav_env.env("SNOV_USER_SECRET"),
    }, timeout=20)
    _token = r.json()["access_token"]
    _token_ts = time.time()
    return _token


def _snov(method: str, path: str, **kw):
    h = {"Authorization": f"Bearer {_snov_token()}"}
    try:
        r = httpx.request(method, f"{SNOV_API}{path}", headers=h, timeout=30, **kw)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# Hosts that are somebody ELSE's property — a listings portal, a social profile, a free
# page builder. A lead whose "website" is one of these has no domain of its own.
#
# This list used to exist only in rank_priority_leads.py, where it produced a scoring
# signal, while the enrichment and send paths each carried their own shorter copy that
# omitted the portals. On 2026-07-21 that gap sent a lead's outreach to the PORTAL's
# own generic mailbox:
# the lead's website was an aqar.fm profile page, the crawler harvested the PORTAL's
# mailbox, and the "email domain must match site domain" guard endorsed it because it
# matched perfectly. One rule, one place, used by everything that touches a website.
_NOT_OWN_DOMAIN = re.compile(
    r"(^|\.)("
    r"aqar\.fm|bayut\.[a-z.]+|haraj\.com\.sa|opensooq\.com|"
    r"glitch\.me|blogspot\.[a-z.]+|wordpress\.com|wix(site)?\.com|weebly\.com|"
    r"godaddysites\.com|sites\.google\.com|business\.site|linktr\.ee|"
    r"facebook\.com|instagram\.com|twitter\.com|x\.com|linkedin\.com|tiktok\.com|"
    r"snapchat\.com|youtube\.com|wa\.me|whatsapp\.com|google\.com|maps\.app\.goo\.gl"
    r")$", re.I)


def is_own_domain(url: str) -> bool:
    """True only if `url`'s host plausibly belongs to the lead itself.

    Fails closed: an empty or unparseable URL is NOT the lead's own domain.
    """
    return bool(_domain_of(url))


def _domain_of(url: str) -> str:
    """Bare host of `url`, or '' when the host belongs to a third party.

    Returning '' is what suppresses downstream work — crawling for an email,
    spending a Snov credit, trusting an address — so a portal URL reads exactly
    like no website at all, which is what it is.
    """
    if not url:
        return ""
    d = re.sub(r"^https?://", "", url.strip())
    d = re.sub(r"^www\.", "", d).split("/")[0].split(":")[0].lower()
    if "." not in d or _NOT_OWN_DOMAIN.search(d):
        return ""
    return d


FREE_MAIL = {"gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "icloud.com",
             "live.com", "msn.com", "aol.com", "protonmail.com"}


def email_belongs_to(email: str, url: str) -> bool:
    """False only when `email` is on a host that belongs to a THIRD PARTY.

    Deliberately narrow. The first version of this also required the mailbox host to
    equal the website host, and a dry run showed it dropping 9 good leads to catch 1
    bad one: companies legitimately mail from a second domain (site `ipi.com.sa`,
    mail `ipi.sa`; site `cstc.sa`, mail `cstc.me`). A mismatch between two PRIVATE
    domains is normal. What is never normal is a mailbox on a listings portal or a
    social network — nobody's corporate mail lives at aqar.fm — and that is the case
    that actually sent one company's outreach to another on 2026-07-21.

    Mismatch between private domains is surfaced by `email_domain_mismatch` instead,
    which warns without suppressing the send.
    """
    email = (email or "").strip().lower()
    if "@" not in email:
        return False
    host = email.rsplit("@", 1)[-1]
    return bool(host) and not _NOT_OWN_DOMAIN.search(host)


def email_domain_mismatch(email: str, url: str) -> bool:
    """True when a valid-looking address sits on a different private domain than the site.

    Advisory only — worth a human glance in the approval table, not worth a drop.
    """
    host = (email or "").strip().lower().rsplit("@", 1)[-1]
    own = _domain_of(url)
    if not host or not own or host in FREE_MAIL:
        return False
    return not (host == own or host.endswith("." + own) or own.endswith("." + host))


def _pick_email(emails: list[str]) -> str:
    for prefix in ("info@", "contact@", "sales@", "admin@"):
        for e in emails:
            if e.lower().startswith(prefix):
                return e
    return emails[0] if emails else ""


def snov_domain_email(domain: str) -> str:
    """Best email for a domain via v2 domain search (async start -> poll)."""
    start = _snov("POST", "/v2/domain-search/domain-emails/start", data={"domain": domain})
    task_hash = (start.get("meta") or {}).get("task_hash") if isinstance(start, dict) else None
    if not task_hash:
        return ""
    for _ in range(4):
        time.sleep(SNOV_DELAY + 2)
        res = _snov("GET", f"/v2/domain-search/domain-emails/result/{task_hash}")
        if isinstance(res, dict) and res.get("data"):
            return _pick_email([i["email"] for i in res["data"] if i.get("email")])
        if isinstance(res, dict) and res.get("status") in ("completed", "finished"):
            break
    return ""


def snov_verify(email: str) -> str:
    """smtp_status for an email ('valid'/'unknown'/'not_valid'/'' on failure)."""
    start = _snov("POST", "/v2/email-verification/start", data={"email": email})
    task_hash = (start.get("meta") or {}).get("task_hash") if isinstance(start, dict) else None
    if not task_hash:
        return ""
    for _ in range(3):
        time.sleep(SNOV_DELAY)
        res = _snov("GET", f"/v2/email-verification/result?task_hash={task_hash}")
        if isinstance(res, dict) and res.get("data"):
            item = res["data"][0] if isinstance(res["data"], list) else res["data"]
            return (item.get("smtp_status") or "") if isinstance(item, dict) else ""
    return ""


def enrich_leads(leads: list[dict]) -> int:
    """Attach email/email_status to lead dicts (in place). Returns #emails found.
    Idempotent: skips leads already carrying an email or a snov_checked marker."""
    found = 0
    todo = [l for l in leads if not l.get("email") and not l.get("snov_checked")]
    if not todo:
        return 0
    print(f"  Snov enrichment: {len(todo)} leads to check…")
    for i, lead in enumerate(todo, 1):
        domain = _domain_of(lead.get("website") or "")
        lead["snov_checked"] = time.strftime("%Y-%m-%d")
        if not domain:
            lead["email_status"] = "no_domain"
            continue
        email = snov_domain_email(domain)
        if not email:
            lead["email_status"] = "no_emails_in_snov"
            print(f"    [{i}/{len(todo)}] {domain}: none")
            continue
        lead["email"] = email
        lead["email_status"] = "found_unverified"
        found += 1
        print(f"    [{i}/{len(todo)}] {domain}: {email} (found_unverified)")
    return found


# ── Twenty CRM (direct HTTP; only Mjeed's records, ever) ─────────────────────

def _crm_h() -> dict:
    return {"Authorization": f"Bearer {nav_env.env('TWENTY_TOKEN')}",
            "Content-Type": "application/json"}


def crm_people_fields(node_fields: str) -> list[dict]:
    """Every one of Mjeed's people, with WHATEVER node fields you ask for. Always paginated.

    Exists because ad-hoc `people(first:200)` queries silently truncate: the CRM holds ~912
    people, so an unpaginated read returns an arbitrary slice and omits the rest without any
    error. On 2026-07-20 that produced two confident false reports of data loss — records
    that were present the whole time simply were not in the sample. Reach for this instead of
    hand-writing a query, so the paging is not optional.

        crm_people_fields("id name{firstName lastName} jobTitle emails{primaryEmail}")
    """
    query = ("query P($first:Int!,$after:String){people(first:$first,after:$after){"
             "edges{node{" + node_fields + " createdBy{name}}}"
             "pageInfo{hasNextPage endCursor}}}")
    rows, cursor = [], None
    while True:
        variables: dict = {"first": 200}
        if cursor:
            variables["after"] = cursor
        page = httpx.post(f"{CRM_BASE}/graphql", headers=_crm_h(),
                          json={"query": query, "variables": variables},
                          timeout=40).json()["data"]["people"]
        rows += [e["node"] for e in page["edges"]]
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    return [r for r in rows if "mjeed" in ((r.get("createdBy") or {}).get("name") or "").lower()]


def _crm_people() -> list[dict]:
    """All of Mjeed's people with their company (GraphQL — REST paging is broken)."""
    q = ("query P($first:Int!,$after:String){people(first:$first,after:$after){"
         "edges{node{id name{firstName lastName} sector leadStatus createdAt "
         "emails{primaryEmail} phones{primaryPhoneNumber} createdBy{name} "
         "company{id name sector domainName{primaryLinkUrl}}}}"
         "pageInfo{hasNextPage endCursor}}}")
    rows, cursor = [], None
    while True:
        v: dict = {"first": 200}
        if cursor:
            v["after"] = cursor
        d = httpx.post(f"{CRM_BASE}/graphql", headers=_crm_h(),
                       json={"query": q, "variables": v}, timeout=40).json()["data"]["people"]
        rows += [e["node"] for e in d["edges"]]
        if d["pageInfo"]["hasNextPage"]:
            cursor = d["pageInfo"]["endCursor"]
        else:
            break
    return [r for r in rows if "mjeed" in ((r.get("createdBy") or {}).get("name") or "").lower()]


def _patch_person(pid: str, payload: dict) -> bool:
    r = httpx.patch(f"{CRM_BASE}/rest/people/{pid}", headers=_crm_h(),
                    json=payload, timeout=30)
    return r.status_code < 300


def normalize_crm_people() -> int:
    """Fill missing sector (from company) + leadStatus for Mjeed's people."""
    fixed = 0
    for p in _crm_people():
        payload: dict = {}
        if not p.get("sector") and (p.get("company") or {}).get("sector"):
            payload["sector"] = p["company"]["sector"]
        if not p.get("leadStatus"):
            payload["leadStatus"] = "Not Contacted"
        if payload and _patch_person(p["id"], payload):
            fixed += 1
    print(f"  CRM normalize: fixed {fixed} people (sector/leadStatus)")
    return fixed


def enrich_crm_not_contacted() -> int:
    """Snov emails for Not Contacted people without one (company domain needed)."""
    found = 0
    todo = [p for p in _crm_people()
            if p.get("leadStatus") == "Not Contacted"
            and not (p.get("emails") or {}).get("primaryEmail")
            and _domain_of(((p.get("company") or {}).get("domainName") or {}).get("primaryLinkUrl") or "")]
    if not todo:
        print("  CRM enrichment: nothing to do")
        return 0
    print(f"  CRM Snov enrichment: {len(todo)} people to check…")
    for i, p in enumerate(todo, 1):
        domain = _domain_of(p["company"]["domainName"]["primaryLinkUrl"])
        email = snov_domain_email(domain)
        label = (p.get("company") or {}).get("name") or p["id"]
        if email and _patch_person(p["id"], {"emails": {"primaryEmail": email}}):
            found += 1
            print(f"    [{i}/{len(todo)}] {label} ({domain}): {email}")
        else:
            print(f"    [{i}/{len(todo)}] {label} ({domain}): none")
    return found


def not_contacted_leads(verticals: list[str]) -> list[dict]:
    """Mjeed's Not Contacted people in the given verticals — deterministic
    selection done HERE so the cloud task never queries/filters the CRM itself
    (agents misread createdBy variants and undercount)."""
    out = []
    for p in _crm_people():
        if p.get("leadStatus") != "Not Contacted" or p.get("sector") not in verticals:
            continue
        name = " ".join(x for x in [(p.get("name") or {}).get("firstName"),
                                    (p.get("name") or {}).get("lastName")] if x).strip()
        phone = (p.get("phones") or {}).get("primaryPhoneNumber") or ""
        out.append({
            "person_id": p["id"],
            "company": (p.get("company") or {}).get("name") or name,
            "contact_name": name if name != ((p.get("company") or {}).get("name") or "") else "",
            "sector": p["sector"],
            "email": (p.get("emails") or {}).get("primaryEmail") or "",
            "phone": phone,
            "website": ((p.get("company") or {}).get("domainName") or {}).get("primaryLinkUrl") or "",
            # Per-lead pain from the lead's own reviews, phone-matched to the scrape
            # pool. Empty for leads we did not scrape — those fall back to general.
            "pain_line": scrape_pain_index().get(_phone9(phone), ""),
        })
    return out


if __name__ == "__main__":
    # Manual run = the full CRM prep (what the console does before an outreach task).
    normalize_crm_people()
    enrich_crm_not_contacted()

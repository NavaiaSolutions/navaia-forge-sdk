#!/usr/bin/env python3
"""Idempotent CRM writes for the discovery pipeline — upsert, not create.

## Why this exists rather than reusing import_selected_leads

`import_selected_leads.create_company/create_person` only ever POST. That is correct for a
one-shot migration and wrong for discovery, which is designed to run continuously: the
second pass over the same lead would create a second company, and the CRM is shared
production. Discovery re-visits leads by design (a site that had no team page in June may
have one in August), so every write here has to be find-then-PATCH-or-POST.

Identity resolution, in descending order of trust:

  1. `known_id`  — the company id this place_id resolved to on a previous run, read from
                   `discovery_state.json`. Exact. Twenty has no `placeId` field and one
                   could not be added, so our own state carries that identity instead —
                   see the note above `company_body` for why not a CRM field.
  2. `domainName`— strong, but companies share hosts (agency-built SMB sites) so it is
                   checked as a normalized host, not a substring.
  3. normalized name — last resort, diacritics and legal forms stripped. Weakest: Saudi SMB
                   names repeat heavily, so a name-only match additionally requires the
                   phone to agree before it is accepted.

## Two rules inherited from incidents, not invented here

**Never erase.** A pass that finds nothing must not overwrite a value an earlier pass
established. Enrichment is additive and sources are flaky; a site that 503s for one run
would otherwise blank a good email. Applied per field, in `_merge_fields`.

**Field-tolerant.** Twenty rejects the whole request when one custom field is unknown, so a
single unsupported field would cost an entire lead's enrichment. On a 400 the write is
retried with core fields only and the rejected names are printed — a partial record beats a
lost one, provided the loss is reported rather than swallowed.

Constants (`CREATED_BY`, `intl_phone`, `lead_score`) are IMPORTED from
`import_selected_leads`, never retyped: `CREATED_BY["name"]` carries an intentional trailing
space in `"Mjeed using "` elsewhere in the codebase, and a re-typed copy would silently
drift from the value every existing record was created with.
"""
from __future__ import annotations

import os
import re
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx

import nav_env
from import_selected_leads import CREATED_BY, headers, intl_phone, lead_score

CRM = nav_env.crm_base()

# Core fields are the ones Twenty is known to accept on a stock schema. Anything outside
# this set is "extended" and gets dropped on a 400 retry.
CORE_COMPANY = {"name", "address", "createdBy", "domainName"}
CORE_PERSON = {"name", "companyId", "createdBy", "phones", "emails", "leadStatus"}

_LEGAL = ["شركة", "مؤسسة", "مكتب", "معهد", "مركز", "co.", "llc", "ltd", "inc"]

# Explicit seniority words only. Matching "مدير" (manager) is deliberate — in a Saudi SMB
# the manager usually is the buyer — but nothing is inferred from a title we merely suspect.
DECISION_ROLE_WORDS = (
    "مدير عام", "الرئيس التنفيذي", "المدير التنفيذي", "مالك", "شريك", "مؤسس", "رئيس مجلس",
    "مدير", "CEO", "Founder", "Owner", "Partner", "Managing Director", "General Manager",
)

# ── What this pipeline writes, and what it deliberately does NOT ──────────────────────
#
# Audited against the live schema on 2026-07-21 by reading a real record of each object.
# The rule: a field is filled only when discovery has a REAL source for it. Everything
# else stays blank, because a plausible-looking guess in a shared CRM is worse than an
# empty cell — it cannot be distinguished from evidence later.
#
# company: name, address, sector, domainName (own site only), employeeCount, linkedinLink
#   NOT annualRevenue      — no honest source; a scrape cannot know revenue
#   NOT priority           — owned by rank_priority_leads, not by discovery
#   NOT accountOwnerId / ownerMemberId — human assignment
#
# person:  name, emails, phones, jobTitle, decisionMaker, sector, leadSource, leadScore,
#          leadStatus (on CREATE only), companyId, linkedinLink
#   NOT lastContactedAt / followUpCount / followUpDueAt — owned by the SEND pipeline.
#       Discovery writing these would fake contact history and corrupt follow-up timing.
#   NOT leadStatus on UPDATE — see NEVER_UPDATE; it would re-message a contacted lead.


def norm_name(n: str) -> str:
    s = (n or "").lower().strip()
    for token in _LEGAL:
        s = s.replace(token, " ")
    s = re.sub(r"[ً-ْـ]", "", s)  # Arabic diacritics + tatweel
    return re.sub(r"\s+", " ", s).strip()


def norm_host(url: str) -> str:
    host = (urlparse(url if "://" in (url or "") else f"https://{url}").netloc or "").lower()
    return host[4:] if host.startswith("www.") else host


def norm_phone(p: str) -> str:
    d = re.sub(r"\D", "", p or "")
    return d[-9:] if len(d) >= 9 else ""


# ── reads ────────────────────────────────────────────────────────────────────────────

def _get(path: str, params: dict | None = None) -> dict:
    r = httpx.get(f"{CRM}{path}", headers=headers(), params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()


def all_companies(page_size: int = 60) -> list[dict]:
    """Every company, PAGINATED.

    An unpaginated read returns an arbitrary slice and has twice produced confident, wrong
    reports about this CRM's contents. A verification step that is itself unverified is
    worse than none, because it manufactures confidence.
    """
    out: list[dict] = []
    cursor = None
    while True:
        params = {"limit": page_size}
        if cursor:
            params["starting_after"] = cursor
        payload = _get("/rest/companies", params)
        batch = payload.get("data", {}).get("companies", [])
        out.extend(batch)
        info = payload.get("pageInfo") or {}
        if not batch or not info.get("hasNextPage"):
            return out
        cursor = info.get("endCursor")
        if not cursor:
            return out


def find_company(lead: dict, index: list[dict] | None = None,
                 known_id: str = "") -> dict | None:
    """Resolve a lead to an existing company record, or None.

    `known_id` is the company id this exact place_id resolved to on a previous run, read
    from `discovery_state.json`. It stands in for the `placeId` field the CRM does not
    have, and it is the ONLY exact key available — so it is tried first.
    """
    companies = all_companies() if index is None else index
    host = norm_host(lead.get("website") or "")
    name = norm_name(lead.get("name") or "")
    phone = norm_phone(lead.get("phone") or "")

    if known_id:
        for c in companies:
            if c.get("id") == known_id:
                return c
    if host:
        for c in companies:
            if norm_host((c.get("domainName") or {}).get("primaryLinkUrl") or "") == host:
                return c
    if name:
        for c in companies:
            if norm_name(c.get("name") or "") != name:
                continue
            # Name alone is too weak in this market. Require phone agreement, or accept
            # only when neither side has a phone to contradict the match.
            cphone = norm_phone((c.get("phone") or {}).get("primaryPhoneNumber")
                                if isinstance(c.get("phone"), dict) else c.get("phone") or "")
            if not phone or not cphone or phone == cphone:
                return c
    return None


# ── writes ───────────────────────────────────────────────────────────────────────────

# Fields a discovery pass may FILL when empty but must never CHANGE when already set.
#
# "Never erase" was originally about blanks, and that is only half the hazard. The other
# half is a non-blank value quietly replacing a better non-blank value — which does not
# look like data loss in any log, because something was always there. A live dry run on
# 2026-07-21 queued a PATCH rewriting a known contact's name to the company name, since
# `person_body` falls back to the company name when no person is found.
#
# The test for membership here: would a human, or a better-informed earlier pass, plausibly
# have curated this field? A scrape must not outrank that. Derived fields (leadScore) and
# facts the scrape genuinely owns (placeId, address, sector) stay updatable.
COMPANY_FILL_ONLY = {"name"}          # renaming a company from a scrape variant is damage
PERSON_FILL_ONLY = {"name", "emails", "phones", "jobTitle", "leadSource"}

# Never written on an UPDATE at all, at any time.
NEVER_UPDATE = {
    "createdBy",     # provenance belongs to whoever created the record
    "leadStatus",    # would reset a contacted lead to "Not Contacted" and re-message them
}


def _merge_fields(existing: dict, fresh: dict, fill_only: set[str] = frozenset()) -> dict:
    """The delta to PATCH: additive by default, never destructive.

    Three rules, in order:
      1. A blank fresh value is dropped — nothing found this pass leaves what is there.
      2. A no-op is dropped — identical writes only add risk of a schema rejection.
      3. A `fill_only` field is dropped when the record already has ANY value for it.
    """
    out = {}
    for key, val in fresh.items():
        if val in (None, "", {}, []):
            continue
        if existing.get(key) == val:
            continue
        if key in NEVER_UPDATE:
            continue
        if key in fill_only and _has_value(existing.get(key)):
            continue
        out[key] = val
    return out


def _has_value(v) -> bool:
    """Whether the CRM already holds something for this field.

    Twenty returns composite fields as dicts with empty strings inside
    (`{"primaryPhoneNumber": ""}`), which is truthy as a dict and would defeat a plain
    `if existing.get(key)` check — so unwrap one level before deciding.
    """
    if v in (None, "", {}, []):
        return False
    if isinstance(v, dict):
        return any(_has_value(x) for x in v.values())
    return True


# Twenty names the offending field in its 400 body:
#   {"messages":["Object company doesn't have any \"placeId\" field."]}
_UNKNOWN_FIELD_RE = re.compile(r'have any\s+\\?"([A-Za-z0-9_]+)\\?"\s+field', re.I)


def _write(method: str, path: str, body: dict, core: set[str], label: str,
           _attempt: int = 1) -> str | None:
    """POST/PATCH, surgically dropping only the fields the schema actually rejects.

    The first version of this fell back to CORE fields on any 400, which is too blunt: a
    real run on 2026-07-21 hit an unknown `placeId` and the retry therefore also discarded
    `sector`, a perfectly valid field, so the company's vertical went unwritten. Twenty
    names the offending field in its error body, so drop exactly that one and retry.

    Falls back to core-only when the message cannot be parsed, because a partial record
    still beats a lost one — but only after the surgical path has been tried.
    """
    r = httpx.request(method, f"{CRM}{path}", headers=headers(), json=body, timeout=30)
    if r.status_code in (200, 201):
        return _extract_id(r.json())

    if r.status_code == 400 and _attempt <= 4:
        rejected = {f for f in _UNKNOWN_FIELD_RE.findall(r.text) if f in body}
        if rejected:
            print(f"    WARN {label}: schema has no {sorted(rejected)} — "
                  f"retrying without, keeping everything else")
            trimmed = {k: v for k, v in body.items() if k not in rejected}
            if not trimmed:
                print(f"    ERR {label}: nothing left to write after dropping {sorted(rejected)}")
                return None
            return _write(method, path, trimmed, core, label, _attempt + 1)

        dropped = sorted(set(body) - core)
        if dropped:
            print(f"    WARN {label}: HTTP 400 and the field could not be identified; "
                  f"falling back to CORE fields — server said: {r.text[:160]}")
            trimmed = {k: v for k, v in body.items() if k in core}
            r2 = httpx.request(method, f"{CRM}{path}", headers=headers(), json=trimmed,
                               timeout=30)
            if r2.status_code in (200, 201):
                print(f"    {label}: wrote CORE fields only; NOT stored: {dropped}")
                return _extract_id(r2.json())
            print(f"    ERR {label} core retry HTTP {r2.status_code}: {r2.text[:160]}")
            return None

    print(f"    ERR {label} HTTP {r.status_code}: {r.text[:160]}")
    return None


def _extract_id(payload: dict) -> str | None:
    data = payload.get("data", {})
    for key in ("createCompany", "updateCompany", "createPerson", "updatePerson"):
        if key in data:
            return (data[key] or {}).get("id")
    return data.get("id")


# ── where the Google place id lives, and why NOT in the CRM ──────────────────────────
#
# Twenty's `company` has no `placeId` field, the API key is scoped to data rather than
# schema, and the operator could not add one in the UI. Storing it as a secondary link on
# `domainName` was tried on 2026-07-21 and REVERTED the same day: when the primary link is
# empty Twenty PROMOTES a secondary to primary, so two companies ended up with a Google
# Maps URL as their website — the same class of wrong data we filter portals to avoid.
#
# So the place id stays in `discovery_state.json`, which we own, is atomic, and already
# keys every lead by exactly that id. Cross-run identity therefore resolves state-first
# (place_id -> company_id, exact) and falls back to domain/name+phone against the CRM.
# Nothing is written to a field that does not mean what we are putting in it.
#
# Rejected alternatives, recorded so this is not re-litigated:
#   * A Note — costs one extra query per company to read back (1196) to rebuild an index a
#     list query gives us free.
#   * Squatting on `priority` — puts data where nobody would look for it and collides with
#     that field's real use.


def company_body(lead: dict, vertical: str, existing: dict | None = None) -> dict:
    body: dict = {
        "name": lead.get("name", ""),
        "sector": vertical,
        "createdBy": CREATED_BY,
    }
    if (addr := (lead.get("address") or "").strip()):
        body["address"] = {"addressStreet1": addr}

    # Only a company's OWN site goes here. discover.own_website() has already stripped
    # portal/social listings, so anything arriving is a real domain.
    if (w := (lead.get("website") or "").strip()):
        prior = (existing or {}).get("domainName") or {}
        body["domainName"] = {
            "primaryLinkUrl": (prior.get("primaryLinkUrl") or "").strip()
                              or (w if w.startswith("http") else "https://" + w),
            "primaryLinkLabel": (prior.get("primaryLinkLabel") or "").strip(),
            "secondaryLinks": [l for l in (prior.get("secondaryLinks") or []) if l],
        }

    if (li := (lead.get("linkedin") or "").strip()):
        body["linkedinLink"] = {"primaryLinkUrl": li}

    # The schema field is `employeeCount`, not `employees` — sending the wrong name made
    # every sized company fall into the 400 retry path and lose the headcount silently.
    if (size := lead.get("employee_count")):
        body["employeeCount"] = size
    return body


def person_body(lead: dict, vertical: str, company_id: str) -> dict:
    person = lead.get("person") or {}
    pname = (person.get("name") or "").strip()
    if pname:
        toks = pname.split()
        first, last = toks[0], " ".join(toks[1:])
    else:
        first, last = lead.get("name", ""), ""
    body: dict = {
        "name": {"firstName": first, "lastName": last},
        "companyId": company_id,
        "sector": vertical,
        "leadSource": lead.get("lead_source", ""),
        "leadStatus": "Not Contacted",
        "leadScore": lead_score(lead),
        "createdBy": CREATED_BY,
    }
    if (role := (person.get("role") or "").strip()):
        body["jobTitle"] = role
        # `decisionMaker` is a real boolean on the person object. Set it ONLY from an
        # explicit seniority word in the scraped role — never inferred from seniority we
        # merely suspect. A wrong True here aims outreach at someone who cannot buy.
        if any(k in role for k in DECISION_ROLE_WORDS):
            body["decisionMaker"] = True
    if (li := (person.get("linkedin") or "").strip()):
        body["linkedinLink"] = {"primaryLinkUrl": li}
    phone = intl_phone(person.get("phone") or "") or intl_phone(lead.get("phone", ""))
    if phone:
        body["phones"] = {"primaryPhoneNumber": phone}
    if (em := (person.get("email") or "").strip()):
        body["emails"] = {"primaryEmail": em}
    return body


def upsert_company(lead: dict, vertical: str, index: list[dict] | None = None,
                   dry_run: bool = False, known_id: str = "") -> tuple[str | None, str]:
    """Return (company_id, 'created'|'updated'|'unchanged'|'skipped')."""
    existing = find_company(lead, index, known_id)
    body = company_body(lead, vertical, existing)

    if existing is None:
        if dry_run:
            print(f"    [dry-run] CREATE company {body.get('name')!r}")
            return None, "created"
        return _write("POST", "/rest/companies", body, CORE_COMPANY, "company"), "created"

    delta = _merge_fields(existing, body, COMPANY_FILL_ONLY)
    if not delta:
        return existing.get("id"), "unchanged"
    if dry_run:
        print(f"    [dry-run] PATCH company {existing.get('id')} fields={sorted(delta)}")
        return existing.get("id"), "updated"
    _write("PATCH", f"/rest/companies/{existing['id']}", delta, CORE_COMPANY, "company")
    return existing.get("id"), "updated"


def upsert_person(lead: dict, vertical: str, company_id: str,
                  dry_run: bool = False) -> tuple[str | None, str]:
    """Upsert the person within the company, identified by phone, else by email.

    Phone is the identity for a SCRAPED lead, which is where this started: a Maps listing
    has a number and rarely an address. A lead sourced from Snov is the mirror image — it
    carries an email and no phone at all — and with only a phone check that lead matched
    nothing, so every re-run CREATED the same human again. The duplicate is not cosmetic:
    two records for one person means two outreach sends to one inbox.

    Email is only consulted when phone yields nothing, so scraped-lead behaviour is
    unchanged. Both are exact-match on a normalised value; neither guesses from a name,
    which is far too weak an identity in this market to merge records on.
    """
    body = person_body(lead, vertical, company_id)
    want = norm_phone((body.get("phones") or {}).get("primaryPhoneNumber", ""))
    want_email = ((body.get("emails") or {}).get("primaryEmail") or "").strip().lower()

    existing = None
    # In a dry run the company was never created, so there is no id to filter people by.
    # Querying anyway sends `companyId[eq]:` empty and the CRM answers 400 — a scary
    # warning about a lookup that was never meaningful in the first place.
    if company_id and (want or want_email):
        try:
            payload = _get("/rest/people", {"filter": f"companyId[eq]:{company_id}",
                                            "limit": 60})
            people = payload.get("data", {}).get("people", [])
            if want:
                for p in people:
                    if norm_phone((p.get("phones") or {}).get("primaryPhoneNumber", "")) == want:
                        existing = p
                        break
            if existing is None and want_email:
                for p in people:
                    emails = p.get("emails") or {}
                    known = [(emails.get("primaryEmail") or "")]
                    known += list(emails.get("additionalEmails") or [])
                    if any((e or "").strip().lower() == want_email for e in known):
                        existing = p
                        break
        except httpx.HTTPError as e:
            print(f"    WARN person lookup failed ({e}); treating as new")

    if existing is None:
        if dry_run:
            print(f"    [dry-run] CREATE person {body['name']}")
            return None, "created"
        return _write("POST", "/rest/people", body, CORE_PERSON, "person"), "created"

    delta = _merge_fields(existing, body, PERSON_FILL_ONLY)
    if not delta:
        return existing.get("id"), "unchanged"
    if dry_run:
        print(f"    [dry-run] PATCH person {existing.get('id')} fields={sorted(delta)}")
        return existing.get("id"), "updated"
    _write("PATCH", f"/rest/people/{existing['id']}", delta, CORE_PERSON, "person")
    return existing.get("id"), "updated"


def _self_test() -> int:
    """Prove the merge cannot destroy data. No network, no writes — safe to run anywhere.

    Each case is a real hazard observed or reasoned about against live data, not a
    hypothetical. Fixtures use invented names and @acme-demo.test addresses.
    """
    cases = [
        # (label, existing, fresh, fill_only, expected_delta)
        ("blank never erases",
         {"jobTitle": "المدير"}, {"jobTitle": ""}, set(), {}),
        ("no-op dropped",
         {"sector": "Real Estate"}, {"sector": "Real Estate"}, set(), {}),
        ("company-name placeholder cannot rename a known person",
         {"name": {"firstName": "سارة", "lastName": "القحطاني"}},
         {"name": {"firstName": "مكتب الريادة", "lastName": ""}},
         PERSON_FILL_ONLY, {}),
        ("a new person's name IS written when the record has none",
         {"name": {"firstName": "", "lastName": ""}},
         {"name": {"firstName": "سارة", "lastName": "القحطاني"}},
         PERSON_FILL_ONLY, {"name": {"firstName": "سارة", "lastName": "القحطاني"}}),
        ("a curated email is not replaced by a scraped one",
         {"emails": {"primaryEmail": "sara@acme-demo.test"}},
         {"emails": {"primaryEmail": "info@acme-demo.test"}},
         PERSON_FILL_ONLY, {}),
        ("an empty email IS filled",
         {"emails": {"primaryEmail": ""}},
         {"emails": {"primaryEmail": "info@acme-demo.test"}},
         PERSON_FILL_ONLY, {"emails": {"primaryEmail": "info@acme-demo.test"}}),
        ("contacted leads are never reset to Not Contacted",
         {"leadStatus": "Contacted"}, {"leadStatus": "Not Contacted"}, set(), {}),
        ("provenance is never re-stamped",
         {"createdBy": {"name": "Mjeed"}}, {"createdBy": CREATED_BY}, set(), {}),
        ("a company is never renamed from a scrape variant",
         {"name": "مكتب الريادة العقارية"}, {"name": "مكتب الريادة"},
         COMPANY_FILL_ONLY, {}),
        ("facts the scrape owns still update",
         {"placeId": ""}, {"placeId": "ChIJ_demo"}, COMPANY_FILL_ONLY,
         {"placeId": "ChIJ_demo"}),
        ("derived score still updates",
         {"leadScore": 40}, {"leadScore": 75}, PERSON_FILL_ONLY, {"leadScore": 75}),
    ]
    failures = 0
    for label, existing, fresh, fill_only, expected in cases:
        got = _merge_fields(existing, fresh, fill_only)
        ok = got == expected
        failures += not ok
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        if not ok:
            print(f"        expected {expected!r}\n        got      {got!r}")
    print(f"\n{len(cases) - failures}/{len(cases)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    print("crm_write — non-destructive merge self-test\n" + "=" * 46)
    sys.exit(_self_test())

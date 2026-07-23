#!/usr/bin/env python3
"""Extract NAMED PEOPLE (name + role + personal email) from a company's own public pages.

Why: every lead contacted on 2026-07-20 was a generic info@ inbox with the company name
duplicated into the Person record — zero named contacts, so every message opened with the
collective «القائمون على … الكرام» and nobody scored the named-decision-maker signal. The
only tool that found real people was Snov, and this pipeline must not use Snov.

Sibling to site_facts.py and follows the same rule: FACTS ONLY, from what the company
published about itself. No inference, no transliteration, no guessed addresses. Every record
carries the sentence it came from so a human can check it.

ANCHOR ON ROLES, NOT NAMES. Scanning for name-shaped tokens matches every proper noun on an
Arabic page — cities, streets, product lines, the founder's home town. Scanning for a ROLE
first and then taking the nearest name is far more precise, because a page that says
"المدير التنفيذي" almost always says who holds it within a few words.

Coverage is honestly modest: many Saudi SMB sites publish no staff at all. A company with no
team page yields nothing, and that is a correct answer, not a failure.

Usage:
    python scripts/people_facts.py <url>          # crawl one site and show people
    python scripts/people_facts.py --self-test    # offline, no network
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from enrich_emails_crawl4ai import EMAIL_RE, JUNK

# Pages where a company introduces its people. Arabic slugs matter more than the English
# ones here — a Saudi SMB is likelier to have «من نحن» than /leadership.
PEOPLE_PATHS = ["team", "our-team", "leadership", "management", "board", "staff",
                "فريق-العمل", "فريقنا", "الفريق", "الإدارة", "مجلس-الإدارة", "من-نحن"]

# Roles worth extracting — the people who can actually buy, plus the ops roles that own the
# pain we sell against. Ordered so the highest-authority match wins when several appear.
_ROLES = [
    (1, re.compile(r"(الرئيس التنفيذي|المدير التنفيذي|الرئيس المؤسس|المؤسس|مالك|صاحب المؤسسة|"
                   r"رئيس مجلس الإدارة|نائب رئيس مجلس الإدارة|العضو المنتدب|شريك مؤسس|شريك)")),
    (1, re.compile(r"\b(chief executive|CEO|COO|CFO|founder|co-?founder|owner|chairman|"
                   r"vice chairman|managing director|managing partner)\b", re.I)),
    (2, re.compile(r"(المدير العام|نائب المدير العام|مدير عام|المدير الإداري)")),
    (2, re.compile(r"\b(general manager|deputy general manager|executive director)\b", re.I)),
    (3, re.compile(r"(مدير العمليات|مدير التشغيل|مدير المشاريع|مدير المرافق|مدير خدمة العملاء|"
                   r"مدير المبيعات|مدير التسويق|مدير المشتريات|مدير الفرع|مدير تطوير الأعمال)")),
    (3, re.compile(r"\b(operations manager|project manager|facilities manager|"
                   r"customer service manager|sales manager|marketing manager|"
                   r"procurement manager|branch manager|business development manager|"
                   r"head of [a-z ]{3,24})\b", re.I)),
]

# Words that look like names but are not people.
_NOT_A_NAME = re.compile(
    r"(شركة|مؤسسة|مجموعة|القابضة|الرئيسية|اتصل|تواصل|الصفحة|خدماتنا|أعمالنا|مشاريعنا|"
    r"المملكة|السعودية|الرياض|جدة|الدمام|حقوق|جميع|المزيد|هنا|home|contact|about|services|"
    r"projects|company|group|riyadh|jeddah|saudi|arabia|rights|reserved|read more|"
    r"llc|ltd|co\.?)", re.I)

# Words that are never part of a personal name. Without this a greedy match happily returns
# a name plus the verb and object that follow it ("<name> يقود فريق").
_STOP_TOKENS = set("""
في من على عن إلى مع ثم قد كل هذا هذه ذلك التي الذي هو هي نحن هم كان يكون
يقود يدير يشرف يعمل لدى منذ خلال بعد قبل حيث كما أيضا الآن هنا
فريق العمل الفريق الإدارة الشركة المؤسسة المجموعة القسم الإدارية التنفيذية
خدمات خدماتنا أعمالنا مشاريعنا رؤيتنا رسالتنا قيمنا تواصل اتصل
and the of for with our team management board company group department
""".split())

# A single token that could be part of a name: Arabic letters, or Latin Title Case.
_TOKEN_AR = re.compile(r"^[ء-ي]{2,}$")
_TOKEN_LAT = re.compile(r"^[A-Z][A-Za-z'’-]{1,}$")

# Honorifics that sit in front of a name and should not be part of it.
_HONORIFIC = re.compile(r"^(الأستاذ|الاستاذ|الدكتور|د\.|م\.|المهندس|السيد|الشيخ|Mr\.?|Dr\.?|Eng\.?)\s+", re.I)

_WINDOW = 120   # chars either side of a role in which a name is considered "adjacent"


def _clean_name(raw: str) -> str:
    name = _HONORIFIC.sub("", " ".join((raw or "").split())).strip(" -–—،,:.")
    return name


def _plausible_name(name: str) -> bool:
    if not name or _NOT_A_NAME.search(name):
        return False
    tokens = name.split()
    if not 2 <= len(tokens) <= 4:
        return False
    if any(ch.isdigit() for ch in name):
        return False
    # Reject ALL-CAPS runs — those are headings, not people. Applies to LATIN ONLY: Arabic
    # has no letter case, so `name.upper() == name` is true for every Arabic name and this
    # test silently rejected all of them.
    if any("A" <= ch <= "Z" or "a" <= ch <= "z" for ch in name) and name == name.upper():
        return False
    return True


def _name_token(token: str) -> bool:
    """Could this single word be part of a person's name?"""
    bare = token.strip(" -–—،,:.()[]«»\"'").lstrip("&")
    if not bare or bare.lower() in _STOP_TOKENS or bare in _STOP_TOKENS:
        return False
    if _NOT_A_NAME.search(bare) or any(ch.isdigit() for ch in bare):
        return False
    return bool(_TOKEN_AR.match(bare) or _TOKEN_LAT.match(bare))


def _nearest_name(text: str, at: int, role_span: tuple[int, int]) -> tuple[str, int]:
    """The name closest to `at`, built from consecutive name-like tokens.

    Token-sliding rather than one greedy regex: a regex matching 2-4 word runs returns the
    role phrase and the following verb ("مدير العمليات المهندس خالد"), because finditer
    takes the longest match at a position and never backtracks to a shorter, valid one.
    Here every maximal run of name-like tokens is a candidate, and its first 2-3 tokens are
    the name — role words and stopwords terminate a run by construction.
    """
    lo, hi = max(0, at - _WINDOW), min(len(text), at + _WINDOW)
    best, best_dist = "", 10**9
    run: list[tuple[str, int]] = []

    def consider(tokens: list[tuple[str, int]]) -> None:
        nonlocal best, best_dist
        if len(tokens) < 2:
            return
        words = [t for t, _ in tokens][:3]
        pos = tokens[0][1]
        # A run that starts inside the role text is the role itself, not a person.
        if role_span[0] <= pos < role_span[1]:
            return
        name = _clean_name(" ".join(words))
        if not _plausible_name(name):
            return
        dist = abs(pos - at)
        if dist < best_dist:
            best, best_dist = name, dist

    offset = lo
    for raw in text[lo:hi].split(" "):
        # The role's OWN words are name-shaped ("مدير", "العمليات"), so without this the run
        # starts at the role and swallows the name that follows it into one candidate. The
        # role must END a run, exactly like a stopword does.
        in_role = role_span[0] <= offset < role_span[1]
        if in_role or not _name_token(raw):
            consider(run)
            run = []
        else:
            run.append((raw.strip(" -–—،,:.()[]«»\"'"), offset))
        offset += len(raw) + 1
    consider(run)
    return best, best_dist


# Saudi MOBILE shape. A person's direct number is almost always a mobile; the company's main
# line is a landline (011…) or a 920/800 unified number — so a mobile sitting next to a named
# person is very likely that person's, which is exactly the "person phone first" rule. The
# company phone is the documented fallback, applied at import, never guessed here.
# 5 + 8 digits, separators optional between any pair — page groupings vary (5x xxx xxxx,
# 55 123 4567, 5xxxxxxxx), so a fixed grouping misses real numbers. Landlines/920 never start
# on a 5 after the prefix, so this stays mobile-only.
_PHONE_RE = re.compile(r"(?:\+?966[\s\-]?|00966[\s\-]?|0)?5(?:[\s\-]?\d){8}")
_PHONE_WINDOW = 70   # tight: a number far from the name is the switchboard, not the person


def _phone_near(text: str, at: int) -> str:
    """A Saudi MOBILE adjacent to the person, normalized to +9665xxxxxxxx, or ''.

    Deliberately narrow: only a mobile, only close to the name. A landline or a distant number
    is the company's and belongs in the company-fallback slot, not on the person.
    """
    lo, hi = max(0, at - _PHONE_WINDOW), min(len(text), at + _PHONE_WINDOW)
    for m in _PHONE_RE.finditer(text[lo:hi]):
        digits = re.sub(r"\D", "", m.group(0))
        if digits.startswith("966"):
            digits = digits[3:]
        digits = digits.lstrip("0")
        if len(digits) == 9 and digits.startswith("5"):
            return "+966" + digits
    return ""


def _email_near(text: str, at: int, name: str) -> str:
    """A personal address adjacent to the name, or ''. NEVER a synthesised pattern.

    Guessing firstname@domain is tempting and wrong: a bounced guess costs sending-domain
    reputation, and we have no way to tell a correct guess from a wrong one.
    """
    lo, hi = max(0, at - _WINDOW * 2), min(len(text), at + _WINDOW * 2)
    first = (name.split() or [""])[0].lower()
    generic = re.compile(r"^(info|contact|sales|admin|support|office|hello|mail)@", re.I)
    for e in EMAIL_RE.findall(text[lo:hi]):
        e = e.strip().lower().rstrip(".")
        if JUNK.search(e) or generic.match(e):
            continue
        local = e.split("@")[0]
        # Accept only when the address plausibly belongs to THIS person.
        if first and (first[:4] in local or local[:4] in first or "." in local):
            return e
    return ""


def extract(markdown: str) -> list[dict]:
    """[{name, role, email, evidence, tier}] for people named on the page. May be empty."""
    text = " ".join((markdown or "").split())
    out: list[dict] = []
    seen: set[str] = set()

    for tier, pattern in _ROLES:
        for m in pattern.finditer(text):
            role = m.group(0).strip()
            name, dist = _nearest_name(text, m.start(), (m.start(), m.end()))
            # No name adjacent to the role means the page states a title but not who holds
            # it — a real and common case. Emit nothing rather than a role with no person.
            if not name or dist > _WINDOW:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            start, end = max(0, m.start() - 90), min(len(text), m.end() + 90)
            out.append({
                "name": name,
                "role": role,
                "email": _email_near(text, m.start(), name),
                "phone": _phone_near(text, m.start()),
                "evidence": text[start:end].strip(),
                "tier": tier,
            })
    out.sort(key=lambda p: p["tier"])
    return out


def from_pages(pages: dict) -> list[dict]:
    """Run extract() over an already-fetched {url: markdown} map, de-duplicated by name."""
    people: dict[str, dict] = {}
    for markdown in pages.values():
        for person in extract(markdown):
            key = person["name"].lower()
            if key not in people:
                people[key] = person
            else:
                # keep the richest record: fill email/phone from a later page if this one has it
                for field in ("email", "phone"):
                    if not people[key].get(field) and person.get(field):
                        people[key][field] = person[field]
    return sorted(people.values(), key=lambda p: p["tier"])


_SELFTEST = [
    ("الرئيس التنفيذي للشركة الأستاذ سالم المطيري يقود فريق العمل منذ 2015",
     "سالم المطيري", "expect name after Arabic role"),
    ("Faisal Alnahdi — Vice Chairman of the Board & CEO. f.alnahdi@acme-demo.test",
     "Faisal Alnahdi", "expect Latin name + personal email"),
    ("نحن شركة رائدة في المملكة العربية السعودية ونقدم خدماتنا في الرياض",
     "", "no role, no person -> nothing"),
    ("المدير التنفيذي: info@company.com للتواصل", "", "role but no name -> nothing"),
    ("مدير العمليات المهندس خالد الشمري k.alshamri@acme-demo.test",
     "خالد الشمري", "honorific stripped, personal email kept"),
]

# (text, expected_phone, why) — person-phone extraction, checked separately from the name cases.
_PHONE_SELFTEST = [
    ("الرئيس التنفيذي الأستاذ سالم المطيري جوال 0501234567 للتواصل المباشر",
     "+966501234567", "mobile next to the named person -> theirs"),
    ("المدير التنفيذي الأستاذ فهد العتيبي، هاتف المكتب 011 456 7890",
     "", "landline near the person is the company's, not a person mobile"),
    ("Managing Director Omar Baeshen  +966 55 123 4567",
     "+966551234567", "spaced +966 mobile normalized"),
]


def _self_test() -> None:
    ok = 0
    for text, expect_name, why in _SELFTEST:
        got = extract(text)
        name = got[0]["name"] if got else ""
        good = (name == expect_name)
        ok += good
        print(f"  {'PASS' if good else 'FAIL'}  {why}")
        print(f"        expected {expect_name!r}, got {name!r}"
              + (f" email={got[0]['email']!r}" if got else ""))
    print(f"\n{ok}/{len(_SELFTEST)} name cases passed")

    pok = 0
    for text, expect_phone, why in _PHONE_SELFTEST:
        got = extract(text)
        phone = got[0]["phone"] if got else ""
        good = (phone == expect_phone)
        pok += good
        print(f"  {'PASS' if good else 'FAIL'}  {why}")
        print(f"        expected {expect_phone!r}, got {phone!r}")
    print(f"\n{pok}/{len(_PHONE_SELFTEST)} phone cases passed")


# The enriched pool carries named people (their phones/emails) and must never be committed to
# the public-mirrored repo, so it lives in its own gitignored file, separate from the tracked
# scrape pool it is built from.
ENRICHED_POOL = "leads_enriched_people.json"


def _fetch_people_deadlined(cache, base: str, budget: int, max_seconds: int):
    """Run one lead's whole multi-page fetch under a wall-clock ceiling.

    The per-FETCH guard inside polite_fetch was not enough: on 2026-07-21 a site's browser
    outlived it and the run hung, because get_many fetches up to `budget` pages and a single
    hung page blocks the loop with no way to interrupt a synchronous call. So the ceiling is
    enforced per LEAD here — the fetch runs in a daemon worker and, if it does not finish in
    time, the lead is abandoned and the loop moves on. The stuck worker is a daemon, so it
    cannot hold the process open; it is reaped at exit. Returns (pages, error).
    """
    import threading
    box: dict = {"pages": None, "err": None}

    def work():
        try:
            box["pages"] = cache.get_many(base, [""] + PEOPLE_PATHS, budget=budget)
        except Exception as e:                      # one bad site must not sink the batch
            box["err"] = str(e)[:120]

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(max_seconds)
    if t.is_alive():
        return None, f"abandoned: no response within {max_seconds}s wall-clock"
    return box["pages"], box["err"]


def enrich_pool(pool_path: str, out_path: str | None = None,
                limit: int | None = None, budget: int = 5,
                max_seconds: int = 120) -> list[dict]:
    """Attach the best named person to each lead in the compact scrape pool.

    Person-first, company-fallback: writes lead["person"] = {name, role, email, phone} when a
    named person is found on the lead's own site (phone may be "" — mobiles are rarely public).
    lead["phone"] (the company number) is left untouched as the fallback. Idempotent: a lead
    that already has a "person" key is skipped, so the run resumes after an interruption. Writes
    to out_path (a gitignored PII file, NOT back into the tracked pool) after each lead, so a
    long scrape is never lost and no named-individual data lands in the tracked source.

    Each lead's fetch runs under a `max_seconds` wall-clock ceiling (default 120s): a site that
    does not answer in time is abandoned with person_error set, and the run continues. This is
    the guard that was missing when the 2026-07-21 run hung on one slow site.
    """
    import polite_fetch
    if out_path is None:
        out_path = os.path.join(os.path.dirname(os.path.abspath(pool_path)), ENRICHED_POOL)
    # Resume from the enriched file if a prior run left one; else start from the tracked pool.
    src = out_path if os.path.exists(out_path) else pool_path
    with io.open(src, encoding="utf-8") as f:
        pool = json.load(f)
    cache = polite_fetch.PageCache()
    attempted = found = 0
    for lead in pool:
        if "person" in lead:                       # already enriched on a prior run
            continue
        site = (lead.get("website") or "").strip()
        if not site:
            lead["person"] = {}                    # no site -> nothing to fetch; mark as done
            continue
        if not site.startswith("http"):
            site = "https://" + site
        base = site.rstrip("/") + "/"
        pages, err = _fetch_people_deadlined(cache, base, budget, max_seconds)
        if err or pages is None:
            lead["person"] = {}
            lead["person_error"] = err or "no pages"
            people = []
        else:
            people = from_pages(pages)
        best = people[0] if people else None
        lead["person"] = ({"name": best["name"], "role": best["role"],
                           "email": best.get("email", ""), "phone": best.get("phone", "")}
                          if best else {})
        attempted += 1
        if best:
            found += 1
            print(f"  + {best['name'][:26]:26} {best.get('phone') or '-':14} "
                  f"{best.get('email') or '-'}  <- {lead['name'][:30]}")
        with io.open(out_path, "w", encoding="utf-8") as f:
            json.dump(pool, f, ensure_ascii=False, indent=1)
        if limit and attempted >= limit:
            break
    print(f"\nenriched {attempted} site-bearing leads; found a named person for {found}")
    print(f"written to {out_path} (gitignored)")
    return pool


def main() -> None:
    if "--self-test" in sys.argv:
        _self_test()
        return
    if "--pool" in sys.argv:
        i = sys.argv.index("--pool")
        pool_path = sys.argv[i + 1]
        limit = None
        if "--limit" in sys.argv:
            limit = int(sys.argv[sys.argv.index("--limit") + 1])
        max_seconds = 120
        if "--max-seconds" in sys.argv:
            max_seconds = int(sys.argv[sys.argv.index("--max-seconds") + 1])
        enrich_pool(pool_path, limit=limit, max_seconds=max_seconds)
        return
    if len(sys.argv) < 2:
        raise SystemExit("usage: people_facts.py <url> | --pool <leads.json> "
                         "[--limit N] [--max-seconds S] | --self-test")

    import polite_fetch
    site = sys.argv[1]
    if not site.startswith("http"):
        site = "https://" + site
    base = site.rstrip("/") + "/"
    cache = polite_fetch.PageCache()
    pages = cache.get_many(base, [""] + PEOPLE_PATHS, budget=5)
    print(f"fetched {len(pages)} page(s)")
    people = from_pages(pages)
    if not people:
        print("no named people published on this site")
        return
    for p in people:
        print(f"  T{p['tier']} {p['name'][:26]:26} {p['role'][:30]:30} "
              f"{p['email'] or '-':28} {p.get('phone') or '-'}")
        print(f"      …{p['evidence'][:110]}…")


if __name__ == "__main__":
    main()

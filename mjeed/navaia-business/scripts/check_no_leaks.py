#!/usr/bin/env python3
"""Refuse to publish real customer data or credentials. Run by the pre-push hook.

Three times on 2026-07-20 real third-party data reached a PUBLIC repository: a customer's
mailbox in a code comment, a named prospect in a commit message, and — after both were
fixed — the same class of mistake again in test fixtures. Every one was written while
explaining a bug, which is exactly when a real example feels most useful.

Discipline demonstrably did not prevent this, so a gate does. This exits non-zero and the
push does not happen.

What it looks for:
  1. Live credentials (OpenRouter/Snov/JWT/bearer shapes, .env contents).
  2. Third-party personal data — addresses at consumer mail hosts, and any name listed in
     the local prospect files, which are gitignored precisely because they are personal
     data under PDPL.
  3. The working-data files themselves, in case a .gitignore rule is ever lost.

It reads prospects.json/contacts.json to know WHICH names are real, so the check adapts as
the CRM grows without anyone maintaining a blocklist. Those files never leave the machine.

Usage:
    python scripts/check_no_leaks.py                 # scan staged + outgoing commits
    python scripts/check_no_leaks.py --range A..B    # scan an explicit range
    python scripts/check_no_leaks.py --all-tracked   # scan the whole working tree
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys

def _repo_root() -> str:
    """The git repo this is being run against, not the one this file lives in.

    The same scanner is deployed inside the public SDK repo at a different depth
    (mjeed/navaia-business/scripts/), where `__file__/..` is NOT the repo root — so
    `git ls-files` and the paths it returns would disagree and the scan would silently
    check nothing. Asking git keeps the two in step wherever the file is checked out.
    """
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             cwd=os.path.dirname(os.path.abspath(__file__)),
                             capture_output=True, text=True, encoding="utf-8", errors="replace")
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except OSError:
        pass
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


ROOT = _repo_root()
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Credential shapes. Deliberately narrow: matching "token" as a word would flag every line
# that merely reads a token from the environment, and a check that cries wolf gets bypassed.
_SECRETS = [
    ("OpenRouter key", re.compile(r"sk-or-v1-[A-Za-z0-9]{16,}")),
    ("OpenAI-style key", re.compile(r"sk-[A-Za-z0-9]{32,}")),
    ("JWT", re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}")),
    ("Bearer literal", re.compile(r"Bearer\s+[A-Za-z0-9._~+/-]{24,}")),
    ("assigned secret", re.compile(
        r"(TWENTY_TOKEN|SNOV_USER_SECRET|ZOHO_PASS|BUSINESS_NF|SECRET_KEY|POSTGRES_PASSWORD)"
        r"\s*=\s*['\"]?[A-Za-z0-9._~+/-]{12,}")),
]

# A third party's mailbox at a consumer host is always personal data. Our own published
# addresses (ops@navaia.sa and the like) are marketing contact details, not a leak.
_CONSUMER_MAIL = re.compile(
    r"[A-Za-z0-9._%+-]+@(gmail|hotmail|outlook|yahoo|icloud|live|aol|proton(mail)?)\.[a-z.]{2,}",
    re.I)

# Files that must never be committed anywhere.
_FORBIDDEN_PATHS = re.compile(
    r"(prospects\.json|contacts\.json|company_size\.json|leads_enriched\.csv|"
    r"leads_enriched_people\.json|"
    # .env.example is a committed template of placeholder values — every repo here allows it
    # explicitly (`!.env.example`). Flagging it made the full scan fail on a file that is
    # supposed to be there, and a check that always fires gets bypassed.
    r"_local_api_key|ONBOARDING_KEYS|\.env$|\.env\.(?!example$)[a-z]+$|discover_state\.json)")

# Sample values in .env.example and scrubbed snapshots match the secret shapes above but
# carry nothing. Flagging them would block every push, and a gate that always fires gets
# bypassed with --no-verify, which is worse than no gate.
_PLACEHOLDER_SECRET = re.compile(
    r"(replace-with|replace_me|changeme|change-me|placeholder|your[-_]|example|"
    r"REDACTED|xxxx|<[^>]+>|\.\.\.)", re.I)

# Placeholders that are obviously not real people, so fixtures stay usable.
_FIXTURE_OK = re.compile(r"(example\.|acme-demo|\.test\b|@test\.|foo@|bar@|user@|someone@)", re.I)


# Tokens that ride along in a name field but are not names. Snov returns qualifications and
# job words inside `last_name` (a real record reads "<first> <last> MBA Candidate"), and
# treating "candidate" as a protected name flags ordinary English prose. A gate that cries
# wolf gets bypassed, which would be worse than no gate at all.
_NOT_A_PERSON_TOKEN = {
    "candidate", "mba", "pmp", "cfm", "cmrp", "cscp", "leed", "iso", "osha", "iosh", "cldm",
    "engineer", "manager", "director", "officer", "chief", "executive", "senior", "junior",
    "company", "group", "limited", "holding", "trading", "contracting", "services",
    "general", "assistant", "supervisor", "consultant", "specialist", "coordinator",
}


# Common given names, transliterated and Arabic. A lone common given name is not identifying
# — there are thousands of them — and flagging it as a leak fires on ordinary prose (a
# docstring example, a transliteration guide). It is only PII when paired with the surname of
# the SAME real person, which the pair matcher below still catches. A distinctive surname on
# its own does still flag. Keeping the gate tight here is what stops it being bypassed wholesale.
_COMMON_GIVEN = {
    "abdullah", "abdallah", "abdulrahman", "abdulaziz", "abdulmajeed", "mohammed", "mohammad",
    "muhammad", "ahmed", "ahmad", "khalid", "faisal", "sultan", "nasser", "salman", "majed",
    "majeed", "turki", "fahad", "saud", "saad", "yousef", "yusuf", "ibrahim", "hamad", "hassan",
    "hussein", "sara", "noura", "nora", "fatima", "aisha", "maryam", "reem", "hana", "lina",
    "عبدالله", "عبدالرحمن", "عبدالعزيز", "عبدالمجيد", "محمد", "أحمد", "احمد", "خالد", "فيصل",
    "سلطان", "ناصر", "سلمان", "ماجد", "تركي", "فهد", "سعود", "سعد", "يوسف", "إبراهيم", "ابراهيم",
    "حمد", "حسن", "حسين", "سارة", "نورة", "فاطمة", "عائشة", "مريم", "ريم", "لينا",
}


# The name/company/phone authority USED to be the local prospect + lead-pool files. Those
# are deleted once their data lands in the CRM (CRM-single-source, 2026-07), which silently
# blinded this guard — names/companies/phones had no source, so the scan passed everything.
# `.leak_denylist.json` restores it: `scripts/build_leak_denylist.py` derives it from the CRM
# (the new single source) and it is gitignored, so the hook stays OFFLINE and the list never
# itself commits. Each source function reads the legacy files AND the denylist, so it works
# whether the local files exist or not.
DENYLIST = ".leak_denylist.json"


def _denylist() -> dict:
    try:
        with io.open(os.path.join(ROOT, DENYLIST), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, AttributeError, TypeError):
        return {}


def real_names() -> set[str]:
    """Distinctive single tokens of real people from the prospect files + CRM denylist.

    Common given names are excluded here and handled only as part of a full pair (see
    `real_name_pairs`), so a lone 'Abdullah' in prose is not treated as a leak while a
    distinctive surname still is.
    """
    # DELIBERATELY NOT the CRM denylist. Single-token matching against ~900 CRM people
    # flags ordinary prose — an agent name ("rashid"), a geographic word ("saudi") — because
    # one common token is low-confidence by nature. The CRM is matched through the
    # high-confidence signals instead: full name PAIRS, whole company names, and phones (see
    # the functions below). Lone-token matching stays scoped to the small curated legacy
    # files, which is what it was designed for.
    names: set[str] = set()
    rows: list = []
    for fname in ("prospects.json", "contacts.json"):
        try:
            with io.open(os.path.join(ROOT, fname), encoding="utf-8") as f:
                rows += json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, AttributeError, TypeError):
            continue
    for row in rows:
        if not isinstance(row, dict):
            continue
        full = (row.get("name") or "").strip()
        for token in full.split():
            cleaned = token.strip(".,-").strip().lower()
            # Only distinctive tokens: a 3-letter fragment matches everything, and a
            # common given name matches half the prose in the repo.
            if (len(cleaned) >= 5 and cleaned not in _NOT_A_PERSON_TOKEN
                    and cleaned not in _COMMON_GIVEN
                    and not _FIXTURE_OK.search(cleaned)):
                names.add(cleaned)
    return names


def real_name_pairs() -> list[tuple[str, str]]:
    """Full (given, surname) pairs of real people — the high-confidence identifier.

    A pair flags only when both tokens of the SAME person appear, so a common given name that
    is safe alone is still caught when it rides next to its real surname.
    """
    pairs: list[tuple[str, str]] = []
    rows = list(_denylist().get("people") or [])
    for fname in ("prospects.json", "contacts.json"):
        try:
            with io.open(os.path.join(ROOT, fname), encoding="utf-8") as f:
                rows += json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, AttributeError, TypeError):
            continue
    for row in rows:
        if not isinstance(row, dict):
            continue
        toks = [t.strip(".,-").strip().lower() for t in (row.get("name") or "").split()]
        toks = [t for t in toks
                if len(t) >= 3 and t not in _NOT_A_PERSON_TOKEN
                and not _FIXTURE_OK.search(t)]
        if len(toks) >= 2:
            pairs.append((toks[0], toks[-1]))
    return pairs


# The scraped lead pool is itself full of real names and phones, so scanning it against itself
# flags every row. It is tracked on purpose (it is the live pain source — see OPEN_ITEMS), so it
# cannot go in _FORBIDDEN_PATHS without blocking every push. Skip it as a SOURCE of truth only.
_LEAD_POOL = "leads_scraped_compact.json"


def real_companies() -> set[str]:
    """Distinctive real company names from the scraped lead pool.

    Added 2026-07-21 after three real leads WITH their mobile numbers were found already public
    in the SDK fork, inside a hardcoded demo list. Every pre-push scan had passed them, because
    the checks above only know about PERSON names. A company is a customer too, and its name in
    a public file is exactly the leak this gate exists to stop.

    Only names of 8+ characters, so a short generic title cannot match ordinary prose.
    """
    out: set[str] = set()
    rows = list(_denylist().get("companies") or [])
    try:
        with io.open(os.path.join(ROOT, _LEAD_POOL), encoding="utf-8") as f:
            rows += json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, AttributeError, TypeError):
        pass
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = (row.get("name") or "").strip()
        if len(name) >= 8 and not _FIXTURE_OK.search(name):
            out.add(name.lower())
    return out


def real_lead_phones() -> set[str]:
    """Last 9 digits of every real lead phone — the part that survives any formatting.

    Matching on the suffix means +966 50 123 4567, 0501234567 and 966501234567 all collide,
    so a number cannot slip through by being written differently.
    """
    out: set[str] = set()
    rows = list(_denylist().get("people") or [])
    try:
        with io.open(os.path.join(ROOT, _LEAD_POOL), encoding="utf-8") as f:
            rows += json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, AttributeError, TypeError):
        pass
    for row in rows:
        if not isinstance(row, dict):
            continue
        digits = re.sub(r"\D", "", row.get("phone") or "")
        if len(digits) >= 9:
            out.add(digits[-9:])
    return out


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              text=True, encoding="utf-8", errors="replace").stdout
    except Exception:
        return ""


def _added_lines(diff: str) -> str:
    """Only the lines a diff ADDS.

    A raw diff also carries every removed line, so the commit that DELETES a leaked secret
    trips the scanner on the secret it is removing — the fix for a leak becomes unpushable
    and the only way out is --no-verify, which disables the whole gate. Removing a secret is
    never a leak; adding one always is.
    """
    return "\n".join(l[1:] for l in diff.splitlines()
                     if l.startswith("+") and not l.startswith("+++"))


def _added_lines_excluding(diff: str, exclude: str) -> str:
    """Added lines, minus those belonging to `exclude`.

    The lead pool is the SOURCE of the company/phone lists and is tracked, so every edit to it
    adds lines that legitimately contain real names — scanning those against the list built from
    the same file would flag it against itself on every push that touches it.
    """
    out, skipping = [], False
    for line in diff.splitlines():
        if line.startswith("+++ "):
            skipping = os.path.basename(line[4:].strip()) == exclude
            continue
        if line.startswith("---") or skipping:
            continue
        if line.startswith("+"):
            out.append(line[1:])
    return "\n".join(out)


def scan_text(label: str, text: str, names: set[str], creds_only: bool = False,
              pairs: list[tuple[str, str]] | None = None,
              companies: set[str] | None = None, phones: set[str] | None = None) -> list[str]:
    hits = []
    for what, pattern in _SECRETS:
        for m in pattern.finditer(text):
            if _PLACEHOLDER_SECRET.search(m.group(0)):
                continue
            hits.append(f"{label}: {what} -> {m.group(0)[:28]}…")
    if creds_only:
        return hits
    for m in _CONSUMER_MAIL.finditer(text):
        if not _FIXTURE_OK.search(m.group(0)):
            hits.append(f"{label}: third-party mailbox -> {m.group(0)}")
    lowered = text.lower()
    for name in names:
        if name in lowered:
            hits.append(f"{label}: real prospect name -> {name}")
    # Full pairs catch a common given name riding next to its real surname, which the
    # distinctive-token pass above deliberately skips.
    for given, surname in (pairs or []):
        if given in lowered and surname in lowered:
            hits.append(f"{label}: real prospect name -> {given} {surname}")
    for company in (companies or []):
        if company in lowered:
            hits.append(f"{label}: real company name -> {company[:44]}")
    if phones:
        digits = re.sub(r"\D", "", text)
        for phone in phones:
            if phone in digits:
                hits.append(f"{label}: real lead phone -> …{phone[-6:]}")
    return hits


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--range", dest="rng", default="")
    ap.add_argument("--all-tracked", action="store_true")
    # A range scan only sees the commits being pushed, so a credential committed before this
    # hook existed stays invisible forever — that is how a live OpenRouter key sat on
    # origin/main until 2026-07-20. Credentials therefore get scanned across the whole tree
    # every push; names and mailboxes stay range-scoped so the pre-existing cleanup backlog
    # does not block unrelated work.
    ap.add_argument("--credentials-only", action="store_true")
    args = ap.parse_args()

    names = real_names()
    pairs = real_name_pairs()
    # Personal-data checks only; --credentials-only scans the whole tree every push and must
    # stay narrow, or the pre-existing cleanup backlog would block unrelated work.
    companies = set() if args.credentials_only else real_companies()
    phones = set() if args.credentials_only else real_lead_phones()
    hits: list[str] = []

    if args.all_tracked:
        for path in _git("ls-files").splitlines():
            if _FORBIDDEN_PATHS.search(path) and not args.credentials_only:
                hits.append(f"TRACKED FILE that must never be committed: {path}")
            # The pool is the SOURCE of the company/phone lists — scanning it against itself
            # would flag every row it legitimately contains.
            src = os.path.basename(path) == _LEAD_POOL
            try:
                with io.open(os.path.join(ROOT, path), encoding="utf-8") as f:
                    hits += scan_text(path, f.read(), names, args.credentials_only, pairs,
                                      set() if src else companies, set() if src else phones)
            except (OSError, UnicodeDecodeError):
                continue
    else:
        diff = _git("diff", "--cached") or _git("diff", "HEAD~1")
        if args.rng:
            diff = _git("diff", args.rng)
            hits += scan_text("commit message", _git("log", "--format=%B", args.rng), names,
                              pairs=pairs, companies=companies, phones=phones)
        for path in (_git("diff", "--cached", "--name-only") or "").splitlines():
            if _FORBIDDEN_PATHS.search(path):
                hits.append(f"STAGED file that must never be committed: {path}")
        # Credentials, mailboxes and person names are scanned across everything added…
        hits += scan_text("diff", _added_lines(diff), names, pairs=pairs)
        # …while company/phone matching skips the pool file, which legitimately holds them.
        hits += scan_text("diff", _added_lines_excluding(diff, _LEAD_POOL), set(),
                          companies=companies, phones=phones)

    if hits:
        print("REFUSING — real data or credentials found:\n")
        for h in sorted(set(hits))[:40]:
            print("   " + h)
        print("\nThis content would become public. Replace real names and addresses with")
        print("invented ones (an @acme-demo.test address is fine), then retry.")
        sys.exit(1)

    print(f"no leaks found ({len(names)} real names checked against)")


if __name__ == "__main__":
    main()

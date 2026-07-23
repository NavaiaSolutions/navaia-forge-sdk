#!/usr/bin/env python3
"""
Distill a gosom/google-maps-scraper result file into a compact JSON lead list.

Keeps only phone-bearing rows; per lead: name, sector guess (from category +
Arabic/English name keywords; empty = let Tariq qualify), address, phone,
website, rating/review_count, place_id, any emails the listing exposes, the
FULL deduped review text, and up to 2 short negative-review snippets as pain
hints (feeds Lina's pain_line — same-listing = trust-locked).

Usage:
    python scripts/distill_scraped_leads.py <scraped.json|csv> [out.json]

## Input formats — all three are accepted

Run gosom with `-json -extra-reviews` to get far more review text per place
(`-extra-reviews` requires `-json`; it is ignored with CSV output). Review text is
the input `review_pains.py` reasons over, so more of it is the point.

Detected automatically, because both formats are in circulation and guessing from
the file extension gets it wrong when someone writes NDJSON to `.txt`:

  * **NDJSON** — one JSON object per line. What gosom `-json` actually emits;
    it is NOT a JSON array, so `json.load()` on the whole file raises.
  * **JSON array** — accepted for hand-assembled files.
  * **CSV** — the legacy path, still read so old `leads_raw.csv` files work.

## Field differences that silently corrupt output if ignored

  * The website column is `web_site` in JSON and `website` in CSV.
  * `user_reviews` is a real list in JSON and a JSON-encoded STRING in CSV.
  * `user_reviews_extended` OVERLAPS `user_reviews` — the same reviewer appears in
    both (verified on live output 2026-07-21). Concatenating double-counts a
    complaint, and `review_pains` decides whether a theme is dominant by COUNTING,
    so a duplicate directly inflates that judgement. They are merged by identity.
"""

import csv
import io
import json
import re
import sys

# Guarded, like every other module here. This rebind used to be UNCONDITIONAL, and that
# silently broke any script importing both this chain and the pipeline_prep chain: two
# TextIOWrapper objects end up over the SAME underlying buffer, the orphaned one is garbage
# collected, and closing it closes the buffer both share. Every print afterwards raises
# "I/O operation on closed file" from a line that has nothing to do with encoding.
# The guard makes the second rebind a no-op, since the first already left stdout as UTF-8.
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
csv.field_size_limit(10_000_000)  # review columns can be huge

# ACTIVE verticals — locked to three by operator decision 2026-07-19.
SECTOR_KEYWORDS = {
    "Real Estate": ["عقار", "أملاك", "real estate", "property"],
    "Contracting & Facilities": ["مقاولات", "صيانة", "مرافق", "contracting", "maintenance", "facilit"],
    "Training Institutes": ["تدريب", "معهد", "training", "institute"],
}

# RETIRED verticals — matched only so they can be DROPPED and counted, never emitted.
RETIRED_KEYWORDS = {
    "Private Clinics": ["أسنان", "جلدية", "تجميل", "علاج طبيعي", "dental", "derma", "cosmetic", "physio"],
    "Finance & Debt Collection": ["تحصيل", "تمويل", "تقسيط", "debt", "finance", "installment"],
}


def guess_sector(name: str, category: str) -> str:
    """Active vertical name, '' if unclassified, or 'RETIRED:<name>' to be dropped."""
    hay = f"{name} {category}".lower()
    for sector, kws in RETIRED_KEYWORDS.items():
        if any(k in hay for k in kws):
            return f"RETIRED:{sector}"
    for sector, kws in SECTOR_KEYWORDS.items():
        if any(k in hay for k in kws):
            return sector
    return ""


# Text that carries no describable pain no matter what star rating it was filed under.
# A 1-star review reading only "Nice" is real — people mis-click, or are sarcastic — and it
# reached outreach as شركة البرج اللامع's sole pain hint on 2026-07-20, guaranteeing a
# generic message. A low rating means the reviewer was unhappy; it does NOT mean the TEXT
# explains why, and only the text is usable downstream.
_PRAISE_ONLY = re.compile(
    r"^\W*(nice|good|great|ok+|fine|excellent|perfect|best|thanks?|thank you|"
    r"ممتاز|جيد|رائع|جميل|زين|تمام|شكرا|شكراً|جزاك الله خير|طيب|حلو|كويس|"
    r"[\U0001F300-\U0001FAFF☀-➿])\W*$", re.I)

# Complaints that map to something NAVAIA actually fixes: nobody answers, slow reply, no
# follow-up, missed calls, unreachable. Hints matching these are ranked FIRST, because only
# two survive and lina_compose can only match a pain that is present in the text it gets.
_RELEVANT = re.compile(
    r"(ما ?رد|ما ?يرد|لا ?يرد|لا ?يردون|ماردوا|ما ?ردوا|يرد علي|"
    r"ما ?يجاوب|لا ?يجيب|ما ?جاوب|"
    r"تأخر|تاخر|متأخر|بطيء|بطي|طولوا|ينتظر|انتظرت|"
    r"ما ?تواصل|لا ?تواصل|التواصل|يتواصل|متابعة|ما ?تابع|"
    r"مغلق|ما ?يفتح|الهاتف|الاتصال|اتصلت|مكالمة|واتس|"
    r"no reply|never answer|no answer|no response|didn'?t reply|didn'?t answer|"
    r"unreachable|slow response|no follow.?up|call(ed)? (them )?many times)", re.I)

# Below this a snippet is too short to describe anything ("سيء", "bad", "🙁").
_MIN_LEN = 25


def all_reviews(row: dict) -> list[dict]:
    """Every review for this listing, deduped, from whichever format the row came in.

    `user_reviews` is a list in gosom's JSON output and a JSON-encoded string in its CSV.
    `user_reviews_extended` (only present with `-extra-reviews`) repeats entries already in
    `user_reviews` rather than containing only the new ones — verified on live output
    2026-07-21, where the same reviewer appeared in both with only the profile-image URL
    differing. Identity is therefore (reviewer name, review text), not the whole dict.

    Deduping is not cosmetic: `review_pains.py` calls a theme dominant on `count >= 2`, so
    one duplicated complaint would be enough to manufacture a dominant theme out of a
    single unhappy customer.
    """
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for key in ("user_reviews", "user_reviews_extended"):
        raw = row.get(key)
        if isinstance(raw, str):
            try:
                raw = json.loads(raw or "[]")
            except json.JSONDecodeError:
                continue
        for rv in (raw or []):
            if not isinstance(rv, dict):
                continue
            text = " ".join((rv.get("Description") or "").split())
            ident = ((rv.get("Name") or "").strip(), text)
            if not text or ident in seen:
                continue
            seen.add(ident)
            out.append({"Name": rv.get("Name") or "", "Rating": rv.get("Rating"),
                        "Description": text, "When": rv.get("When") or ""})
    return out


def negative_reviews(row: dict) -> list[dict]:
    """Low-rated reviews whose TEXT actually describes something.

    A low rating means the reviewer was unhappy; it does NOT mean the text explains why,
    and only the text is usable downstream. This is the free prefilter `review_pains.py`
    runs before spending a single token.
    """
    keep = []
    for rv in all_reviews(row):
        if (rv.get("Rating") or 5) > 2:
            continue
        text = rv["Description"]
        if len(text) < _MIN_LEN or _PRAISE_ONLY.match(text):
            continue
        keep.append(rv)
    return keep


def pain_hints(row: dict, limit: int = 2, max_len: int = 200) -> list[str]:
    """Usable negative-review snippets from the same listing (trust-locked pain).

    A hint is only worth carrying if a human could read it and name the problem. Puts
    complaints matching a pain we actually solve ahead of generic anger, since only
    `limit` survive. `review_pains.py` supersedes this for leads with enough material —
    it stays as the zero-cost fallback.
    """
    candidates = [rv["Description"][:max_len] for rv in negative_reviews(row)]
    # Stable sort: relevant complaints first, original review order preserved within groups.
    candidates.sort(key=lambda t: 0 if _RELEVANT.search(t) else 1)
    return candidates[:limit]


def read_records(path: str) -> list[dict]:
    """Rows from gosom output in whichever of the three formats it is.

    Sniffed from CONTENT, not the extension: NDJSON written to a `.txt`, or a `.json` that
    is really a CSV, both happen, and mis-reading them yields zero leads with no error.
    """
    with io.open(path, encoding="utf-8", newline="") as f:
        head = f.read(4096)
        f.seek(0)
        stripped = head.lstrip()

        if stripped.startswith("["):
            data = json.load(f)
            return [r for r in data if isinstance(r, dict)]

        if stripped.startswith("{"):
            rows = []
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as e:
                    # Report and continue: one truncated final line (a killed scrape) must
                    # not discard every complete record before it.
                    print(f"  WARN {path}:{lineno} unparseable, skipped ({e.msg})")
            return [r for r in rows if isinstance(r, dict)]

        return list(csv.DictReader(f))


def normalise(row: dict) -> dict:
    """One row -> the compact lead shape, reconciling the JSON and CSV column names."""
    # gosom names this `web_site` in JSON and `website` in CSV. Reading only one of them
    # silently drops every website from the other format.
    website = (row.get("web_site") or row.get("website") or "").strip()

    emails = row.get("emails")
    if isinstance(emails, str):
        emails = [e.strip() for e in emails.split(",") if e.strip()]
    emails = [e for e in (emails or []) if e]

    reviews = all_reviews(row)
    return {
        "name": (row.get("title") or "").strip(),
        "sector_guess": "",                      # filled by the caller after the retired check
        "category": (row.get("category") or "").strip(),
        "address": (row.get("address") or "").strip(),
        "phone": (row.get("phone") or "").strip(),
        "website": website,
        "emails": emails,                        # listings sometimes expose one — free, real
        "rating": row.get("review_rating") or "",
        "review_count": row.get("review_count") or "",
        "place_id": row.get("place_id") or "",
        "pain_hints": pain_hints(row),
        # The full negative-review text, kept so review_pains.py can reason over ALL of it.
        # pain_hints caps at 2 and is the wrong input for frequency analysis.
        "negative_reviews": [rv["Description"] for rv in negative_reviews(row)],
        "review_sample": len(reviews),
    }


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: distill_scraped_leads.py <scraped.json|csv> [out.json]")
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else "leads_scraped_compact.json"

    rows = read_records(src)
    leads, seen = [], set()
    dropped_retired: dict[str, int] = {}
    no_phone = 0

    for row in rows:
        lead = normalise(row)
        if not lead["name"] or not lead["phone"]:
            no_phone += 1
            continue
        key = (lead["place_id"] or lead["name"].lower(), lead["phone"])
        if key in seen:
            continue
        seen.add(key)

        sector = guess_sector(lead["name"], lead["category"])
        if sector.startswith("RETIRED:"):
            v = sector.split(":", 1)[1]
            dropped_retired[v] = dropped_retired.get(v, 0) + 1
            continue
        lead["sector_guess"] = sector
        leads.append(lead)

    with io.open(dst, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=1)

    reviewed = sum(1 for l in leads if l["negative_reviews"])
    total_reviews = sum(l["review_sample"] for l in leads)
    print(f"read {len(rows)} rows from {src}")
    print(f"  dropped (no name/phone): {no_phone}")
    for v, n in sorted(dropped_retired.items()):
        print(f"  dropped (RETIRED {v}): {n}")
    print(f"  kept: {len(leads)} leads -> {dst}")
    print(f"  reviews collected: {total_reviews} across {len(leads)} leads "
          f"({reviewed} have usable negative reviews)")

    by_sector: dict[str, int] = {}
    for l in leads:
        by_sector[l["sector_guess"] or "(unclassified)"] = by_sector.get(l["sector_guess"] or "(unclassified)", 0) + 1
    print(f"{len(leads)} phone-bearing leads -> {dst} ({sum(len(json.dumps(l, ensure_ascii=False)) for l in leads)} chars)")
    for s, n in sorted(by_sector.items(), key=lambda x: -x[1]):
        print(f"  {s}: {n}")
    if dropped_retired:
        print("dropped (RETIRED verticals, locked out 2026-07-19):")
        for s, n in sorted(dropped_retired.items(), key=lambda x: -x[1]):
            print(f"  {s}: {n}")


if __name__ == "__main__":
    main()

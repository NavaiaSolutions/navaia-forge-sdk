#!/usr/bin/env python3
"""Extract verifiable facts from a company's OWN website, for outreach personalisation.

Why: review-mined pain is usually the wrong pain. On 2026-07-20 all 9 contacted leads
rendered a GENERAL block — one company's entire review history was the word "Nice", and
الروسان's complaints were about land measurement and refunds, not slow replies. We sell
"you answer too slowly"; being angry about a plot size is not that. Meanwhile we were
already crawling these companies' websites for headcount and throwing the page away.

A company's own site says what it does, where, and at what scale. That is specific, true,
flattering, and free — a far better opener than a stranger's one-star review.

DESIGN RULE: facts only, never adjectives. This module extracts NUMBERS and NAMES the
company published about itself, each with the sentence it came from so a human can check
it. It does not infer, estimate, or characterise. A fact we cannot source is not emitted.

The Arabic phrasing lives here too, one shape per fact type rather than a single skeleton
with a slot — the operator rejects copy where every message is visibly the same sentence
with a word swapped (see workforce/04_outreach_templates.md voice rules). Each opener also
has to LAND on the pain, so the shapes end by setting up volume/load, not by complimenting.
"""
from __future__ import annotations

import re

# Arabic-Indic digits -> ASCII so "١٣ منطقة" matches the same patterns as "13 منطقة".
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

# Each: (fact_key, pattern, (low, high) plausibility bounds for the captured number)
_NUMERIC_FACTS = [
    ("regions", re.compile(
        r"(?:في|تغطي|تغطية|حضور|تواجد|انتشار)\s*(?:أكثر من\s*)?(\d{1,2})\s*"
        r"(?:منطقة|مناطق|مدينة|مدن)"), (2, 20)),
    # The qualifier between "in" and the number is where this quietly fails: goamaken.com
    # says "presence in ALL 13 regions of the Kingdom", and a pattern allowing only "over"
    # missed the single best fact on the page. Accept the common hedges, or none.
    ("regions", re.compile(
        r"(?:present|presence|operating|operates|coverage|covering)\s+(?:in|across)\s+"
        r"(?:all\s+|over\s+|more than\s+|the\s+)*(\d{1,2})\s+"
        r"(?:regions?|cities|provinces|governorates)", re.I), (2, 20)),
    ("branches", re.compile(
        r"(?:أكثر من\s*)?(\d{1,3})\s*(?:فرع|فروع|مكتب|مكاتب)"), (2, 200)),
    ("branches", re.compile(r"(?:over\s+)?(\d{1,3})\s+(?:branches|offices)", re.I), (2, 200)),
    ("projects", re.compile(
        r"(?:أكثر من|أنجزنا|نفذنا|سلّمنا|سلمنا)\s*(\d{2,5})\s*(?:مشروع|مشروعاً|مشاريع)"),
     (10, 100000)),
    ("projects", re.compile(
        r"(?:over|more than|completed)\s+(\d{2,5})\+?\s+projects", re.I), (10, 100000)),
    ("clients", re.compile(
        r"(?:أكثر من|خدمنا|يثق بنا|عملاؤنا)\s*(\d{2,6})\s*(?:عميل|عميلاً|شريك|شركاء)"),
     (20, 1000000)),
    ("clients", re.compile(
        r"(?:over|more than|serving)\s+(\d{2,6})\+?\s+(?:clients|customers)", re.I),
     (20, 1000000)),
    ("years", re.compile(
        r"(?:أكثر من|خبرة تتجاوز|على مدى)\s*(\d{1,2})\s*(?:عام|عاماً|سنة|سنوات)"), (3, 90)),
    ("years", re.compile(
        r"(?:over|more than)\s+(\d{1,2})\s+years?\s+(?:of\s+)?experience", re.I), (3, 90)),
]

# Founding year -> years in business, computed rather than trusted from a marketing line.
_FOUNDED = re.compile(r"(?:تأسست|تأسيس|منذ عام|منذ)\s*(?:في\s*)?((?:19|20)\d{2})"
                      r"|(?:established|founded|since)\s+(?:in\s+)?((?:19|20)\d{2})", re.I)


def _context(text: str, start: int, end: int, width: int = 70) -> str:
    return " ".join(text[max(0, start - width):min(len(text), end + width)].split())


def extract(markdown: str, today_year: int = 2026) -> dict:
    """Return {fact_key: {"value": int, "evidence": "...sentence..."}} from page text.

    Highest plausible value wins per key — a site saying "12 branches" in the nav and
    "over 40 branches" in the about text is describing 40; the smaller number is usually a
    partial list. Values outside the bounds are discarded as pattern collisions (a phone
    number, a postal code, a price).
    """
    text = (markdown or "").translate(_AR_DIGITS)
    facts: dict[str, dict] = {}

    for key, pattern, (low, high) in _NUMERIC_FACTS:
        for m in pattern.finditer(text):
            try:
                value = int(m.group(1))
            except (TypeError, ValueError):
                continue
            if not low <= value <= high:
                continue
            if key not in facts or value > facts[key]["value"]:
                facts[key] = {"value": value, "evidence": _context(text, m.start(), m.end())}

    m = _FOUNDED.search(text)
    if m:
        year = int(m.group(1) or m.group(2))
        age = today_year - year
        if 3 <= age <= 90 and ("years" not in facts or age > facts["years"]["value"]):
            facts["years"] = {"value": age, "evidence": _context(text, m.start(), m.end()),
                              "founded": year}
    return facts


# Arabic numeral agreement (تمييز العدد). Getting this wrong is not cosmetic — "13 مناطق"
# reads as broken Arabic to the executive we are trying to impress, and undoes the point of
# personalising at all. The rule the shapes below rely on:
#   1        singular            منطقة واحدة
#   2        dual                منطقتان
#   3-10     PLURAL genitive     5 مناطق
#   11-99    SINGULAR accusative 13 منطقةً
#   100+     SINGULAR genitive   800 مشروع
_NOUN_FORMS = {
    # key: (plural for 3-10, singular-accusative for 11-99, singular for 100+)
    "regions": ("مناطق", "منطقةً", "منطقة"),
    "branches": ("فروع", "فرعاً", "فرع"),
    "projects": ("مشاريع", "مشروعاً", "مشروع"),
    "clients": ("عملاء", "عميلاً", "عميل"),
    "years": ("سنوات", "عاماً", "عام"),
}


def counted(value: int, key: str) -> str:
    """'13 منطقةً' / '5 مناطق' / '800 مشروع' — the number with its correct noun form."""
    plural, singular_acc, singular = _NOUN_FORMS[key]
    if 3 <= value <= 10:
        return f"{value} {plural}"
    if 11 <= value <= 99:
        return f"{value} {singular_acc}"
    return f"{value} {singular}"


# One shape per fact type. Each states the company's own published scale, then turns it
# toward the load that scale creates — which is the thing we sell against. Deliberately NOT
# one template with a slot: the operator rejects copy where every message is visibly the
# same sentence. No coined verbs (تُؤتمت/نُؤتمت are banned), Arabic commas, no em-dash.
_SHAPES = {
    "regions": "بتغطيتكم {counted} في المملكة، يصلكم يومياً من الاتصالات والاستفسارات ما لا يحتمل التأخير.",
    "branches": "مع {counted}، تتوزّع الاتصالات والاستفسارات على أكثر من نقطة، وتصعب متابعتها كلها في وقتها.",
    "projects": "بعد أكثر من {counted}، يزداد ما يصلكم من طلبات وعروض، ويصعب أن يبقى كل طلبٍ تحت المتابعة.",
    "clients": "بقاعدة تتجاوز {counted}، يصبح الردّ في وقته على كل مستفسرٍ عبئاً حقيقياً على الفريق.",
    "years": "خلال {counted} من العمل، كبرت قاعدة عملائكم، وكبر معها ما يصلكم يومياً من اتصالاتٍ ورسائل.",
}

# Which fact makes the strongest opener when several are present. Scale of OPERATIONS beats
# tenure: coverage and branches imply inbound volume today, while years implies only history.
_PRIORITY = ["regions", "branches", "clients", "projects", "years"]


def opener(facts: dict) -> tuple[str, str]:
    """(arabic_line, fact_key) from the strongest available fact, or ('','') if none."""
    for key in _PRIORITY:
        if key in facts:
            return _SHAPES[key].format(counted=counted(facts[key]["value"], key)), key
    return "", ""


if __name__ == "__main__":
    import io
    import json
    import sys

    if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sample = sys.stdin.read() if not sys.argv[1:] else io.open(sys.argv[1], encoding="utf-8").read()
    f = extract(sample)
    print(json.dumps(f, ensure_ascii=False, indent=1))
    line, key = opener(f)
    print("\nopener [" + key + "]:", line)

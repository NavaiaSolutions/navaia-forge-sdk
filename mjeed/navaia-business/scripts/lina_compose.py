"""Lina's compose logic — relevance-ranked, COUPLED pain->solution block (option B).

The message uses ONE dynamic slot `{{2}}` that always carries a *coupled* pain + the
NAVAIA solution that addresses THAT pain. The rest of the template is fixed and whole
(greeting, impact + compliance, question close, signature).

Decision (per the boss + user rules):
  - The pain is NOT auto-preferred just because it's specific. RELEVANCE wins.
  - specific pain (lead's own reviews, `pain_line` from enrich_reviews.py) is scored by how
    well it maps to a KNOWN, solvable pain in the vertical's library (keyword match) plus a
    small "grounded in real reviews" bonus.
  - general pain has a constant baseline relevance (it's the vertical's dominant pain, always
    at least decently relevant, and keeps the message WHOLE when there's no specific signal).
  - whichever scores higher wins; its coupled solution rides along. If the specific pain maps
    to nothing we can solve (novel / noise), the GENERAL pair wins — the safe, whole default.

`{{2}}` is GENERATED per lead when a pain profile exists (see `generate_block`), and falls
back to this deterministic library otherwise. The library is the FLOOR, not the default: it
is what guarantees publishable copy when the profile is empty, unusable, or off-topic.

Deterministic by design (OPTIMIZATION.md: scripts, not model calls). An optional LLM step is
left as a stub for genuinely novel specific pains; off by default to control spend.

Usage:
    python scripts/lina_compose.py --self-test
    python scripts/lina_compose.py --in leads_enriched.csv --vertical clinics --limit 20
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Tunables (calibratable; exposed on purpose) ─────────────────────────────
GENERAL_RELEVANCE = 1.0     # baseline relevance of the vertical's general pain
GROUNDED_BONUS = 0.6        # bonus for a specific pain that is grounded in real reviews
PER_KEYWORD = 0.6           # relevance added per matched library keyword
# specific wins iff (matched_keywords*PER_KEYWORD + GROUNDED_BONUS) > GENERAL_RELEVANCE
# → one solid keyword match (0.6) + grounded (0.6) = 1.2 > 1.0 → specific wins
# → zero keyword match (novel/noise) = 0.6 < 1.0 → general wins (more relevant)

# ── Per-vertical pain -> solution library ───────────────────────────────────
# Each category coupled: a solvable pain and the EXACT NAVAIA solution for it.
# `general` is the whole/complete default. Specific categories supply the matched
# SOLUTION; the lead's own `pain_line` supplies the PAIN wording when it matches.
LIBRARY: dict[str, dict] = {
    "clinics": {
        "desc": "عيادة خاصة: مكالمات فائتة بعد الإغلاق، حجز وتذكير، إلغاء وتغيّب، دوران موظفي الاستقبال",
        "general": {
            "pain": "بين المكالمات التي تفوت بعد إغلاق العيادة والإلغاءات دون تذكير وتبدّل موظفي الاستقبال، قد يضيع حجزٌ كل يوم",
            "solution": "ونحن إلى جانب فرقكم نُشغّل حلولاً ذكية تتولّى الردّ والحجز والتذكير على مدار الساعة، داخل الدوام وخارجه، دون غياب ولا دوران",
        },
        "categories": {
            "no_show": {
                "triggers": ["حضور", "يحضر", "حضر", "تخلف", "غياب", "ما حضر", "الغاء", "يلغي"],
                "desc": "الإلغاء وعدم الحضور دون إشعار أو تذكير",
                "pain": "الإلغاء وعدم حضور بعض المواعيد دون إشعار",
                "solution": "وإلى جانب فرقكم تتولّى حلولنا الذكية التذكير عبر واتساب والرسائل قبل كل موعد وتأكيده، فيقلّ الإلغاء والتغيّب",
            },
            "after_hours": {
                "triggers": ["الدوام", "دوام", "مغلق", "مساء", "الليل", "بالليل", "فائته", "فاتت"],
                "desc": "أغلب المكالمات الفائتة تصل بعد إغلاق العيادة دون ردّ",
                "pain": "أغلب المكالمات الفائتة تصل مساءً بعد إغلاق العيادة دون ردٍّ أو حجز",
                "solution": "ونحن إلى جانب فرقكم بحلولٍ ذكية تتولّى الردّ والحجز حتى بعد الإغلاق، فيتحوّل كل اتصالٍ مسائي إلى موعدٍ محجوز",
            },
            "slow_reply": {
                "triggers": ["تاخر", "الرد", "يرد", "ردو", "انتظار", "بطء", "بدون رد"],
                "desc": "تأخّر أو انعدام الردّ على الاتصالات والرسائل",
                "pain": "تأخّر الردّ على اتصالات مراجعيكم ورسائلهم",
                "solution": "ونحن نعمل إلى جانب فرقكم بأتمتةٍ ذكية تتولّى الردّ الأول عبر قنواتكم فوراً، فلا ينتظر مراجعكم",
            },
            "booking_hard": {
                "triggers": ["الحجز", "احجز", "صعوب", "صعب", "تعقيد"],
                "desc": "صعوبة حجز المواعيد على المراجعين",
                "pain": "صعوبة حجز المواعيد على مراجعيكم",
                "solution": "ونحن إلى جانب فرقكم نُشغّل أتمتةً تتولّى الحجز والتأكيد، فيسهل على مراجعكم تثبيت موعده",
            },
            "staff_turnover": {
                "triggers": ["موظف", "الموظفين", "تبديل", "دوران", "استقال", "تغير الموظف", "اسلوب"],
                "desc": "دوران موظفي الاستقبال يهزّ ثبات الخدمة وجودتها",
                "pain": "تبدّل موظفي الاستقبال يجعل جودة الردّ والخدمة غير ثابتة",
                "solution": "ونحن إلى جانبكم بحلولٍ ذكية تتولّى الاستقبال بأداءٍ وجودةٍ ثابتين مهما تغيّر الموظفون، بلا غياب ولا دوران",
            },
        },
    },
    "contracting": {
        "desc": "مقاولات وصيانة: رصد المناقصات (اعتماد وفرصة)، تقييم الأهلية، عروض أسعار، عقود القطاع الخاص",
        "general": {
            "pain": "قد تفوت مقاولي التشغيل والصيانة عقودٌ كل أسبوع، لغياب من يرصد المناقصات ويجهّز الردّ في وقته",
            "solution": "ونحن إلى جانب فرقكم نُشغّل أتمتةً ترصد مناقصات اعتماد وفرصة فور نشرها وتُقيّم الأهلية وتجهّز الردّ، بقدرة فريق مناقصاتٍ كامل دون توظيف",
        },
        "categories": {
            "rfq_slow": {
                "triggers": ["عرض سعر", "تسعير", "سعر", "عروض", "العرض", "rfq"],
                "desc": "تأخّر الردّ على طلبات عروض الأسعار",
                "pain": "قد يتأخّر الردّ على طلبات عروض الأسعار حتى يسبقكم غيركم",
                "solution": "ونحن إلى جانب فرقكم نُشغّل أتمتةً تستقبل الطلبات وتردّ عليها ردّاً أوّلياً فور وصولها، فلا يفوتكم طلب",
            },
            "tender_deadline": {
                "triggers": ["مناقص", "عطاء", "العطاء", "الترسيه", "ترسيه", "التسليم", "اعتماد", "فرصه"],
                "desc": "متابعة المناقصات يدوية متقطّعة فتصل العروض متأخرة",
                "pain": "متابعة مناقصات اعتماد وفرصة يدويّةٌ متقطّعة، فيتأخّر العرض عن موعده",
                "solution": "وبأتمتةٍ إلى جانب فرقكم تُرصَد كل منافسةٍ فور نشرها وتُقيَّم أهليّتها ويصلكم موجز قرارها خلال دقائق، فلا يتأخّر عرض",
            },
            "followup_lost": {
                "triggers": ["متابع", "تابع", "معلق", "بدون متابعه", "ما تابع"],
                "desc": "بقاء العروض دون متابعة حتى تبرد",
                "pain": "تبقى بعض عروضكم معلّقةً دون متابعةٍ حتى يفتر الاهتمام بها",
                "solution": "ونحن إلى جانب فرقكم نُشغّل أتمتةً تتابع العروض المعلّقة في وقتها، فيبقى العرض حيّاً حتى الحسم",
            },
            "private_contracts": {
                "triggers": ["قطاع خاص", "ملاك", "المنشات", "مرافق", "عقود مباشره", "عقد صيانه"],
                "desc": "غياب خطٍّ موازٍ لعقود القطاع الخاص مع ملّاك المنشآت",
                "pain": "الاعتماد على المناقصات وحدها، دون خطِّ عقودٍ مباشرٍ مع ملّاك المنشآت والمرافق",
                "solution": "ونحن إلى جانبكم نُشغّل أتمتةً تبني خطّ عقود القطاع الخاص مع ملّاك المنشآت والمرافق، موازياً للمناقصات",
            },
        },
    },
    "finance": {
        "desc": "تمويل وتحصيل ديون: إيراد ميت في المتعثّرات، تحصيل مبكّر قبل التقادم، احتراق المحصّلين، توثيق أمام المنظّم",
        "general": {
            "pain": "الدَّين المتعثّر إيرادٌ ميت، والمتابعة اليدوية تُرهق المحصّلين وتتأخّر حتى يتقادم الدَّين",
            "solution": "وإلى جانب فرقكم تتولّى حلولنا الذكية الاتصال والمراسلة وتوثيق كل وعدٍ بالدفع وفق ضوابط البنك المركزي، فيرتفع التحصيل المبكّر دون توظيفٍ أو احتراق",
        },
        "categories": {
            "aging_debt": {
                "triggers": ["اعمار الديون", "تقادم", "ديون", "متعثر", "المتعثر"],
                "desc": "تقادم أعمار الديون دون متابعة مبكّرة منتظمة",
                "pain": "تقادم أعمار ديونكم قبل أن تصلها متابعةٌ منتظمة",
                "solution": "ونحن نعمل إلى جانب فرقكم بحلولٍ ذكية تتولّى المتابعة المبكّرة على مدار الساعة قبل تقادم الدَّين، فيرتفع التحصيل ويتسارع",
            },
            "reminder": {
                "triggers": ["تذكير", "يذكر", "ينسون", "ينسى", "نسي", "القسط", "اقساط", "الاقساط", "استحقاق"],
                "desc": "عدم تذكير العملاء بمواعيد أقساطهم",
                "pain": "تذكير عملائكم بمواعيد أقساطهم",
                "solution": "ونحن إلى جانب فرقكم نُشغّل أتمتةً تتولّى تذكير عملائكم بأقساطهم قبل استحقاقها، فيقلّ التعثّر",
            },
            "collector_load": {
                "triggers": ["ارهاق", "المحصل", "محصل", "كثره الحالات", "ضغط", "احتراق", "استقال"],
                "desc": "احتراق فرق التحصيل ودورانهم مع كثرة الحالات",
                "pain": "كثرة الحالات تُرهق محصّليكم وتزيد دورانهم",
                "solution": "ونحن إلى جانب فرقكم بحلولٍ ذكية تتولّى المتابعة الروتينية بسعةٍ تتوسّع مع محفظتكم، دون توظيفٍ ولا تدريبٍ ولا دوران، فيتفرّغ فريقكم لما يحتاج تفاوضاً",
            },
            "compliance_docs": {
                "triggers": ["توثيق", "ساما", "المركزي", "امتثال", "تسجيل المكالمات", "المنظم", "شكوى"],
                "desc": "إثبات الامتثال وتوثيق المكالمات أمام المنظّم عبء يدوي",
                "pain": "توثيق المكالمات وإثبات الامتثال أمام المنظّم عبءٌ يدويٌّ مستمر",
                "solution": "ونحن إلى جانبكم نُشغّل حلولاً ذكية تتولّى توثيق كل مكالمةٍ ووعدٍ بالدفع مُقيَّماً ومُثبتاً وفق ضوابط البنك المركزي، فيصبح الامتثال ميزةً لا عبئاً",
            },
            "slow_reply": {
                "triggers": ["تاخر", "الرد", "يرد", "ردو", "بدون رد", "تجاهل", "ما رد", "ما يرد"],
                "desc": "تأخّر أو انعدام الردّ على اتصالات العملاء ورسائلهم",
                "pain": "تأخّر الردّ على اتصالات عملائكم ورسائلهم",
                "solution": "وإلى جانب فرقكم تتولّى حلولنا الذكية الردّ الأول والمتابعة مع عملائكم فوراً، فلا يُهمل عميل",
            },
        },
    },
    "realestate": {
        "desc": "عقار وإدارة أملاك: ردّ فوري على المهتمّين، حملات على قوائم البيع والإيجار، تحصيل إيجار، مناقصات تطوير",
        "general": {
            "pain": "قد ينصرف المهتمّ خلال دقائق إن لم يجد ردّاً، وتبقى قوائم البيع والإيجار دون تواصلٍ صادرٍ ومتابعة",
            "solution": "ونحن إلى جانب فرقكم نُشغّل أتمتةً تتولّى الردّ على المهتمّين، مشترين ومستأجرين، وتدير الحملات على قوائمكم من اليوم الأول، دون عبءٍ على فريقكم",
        },
        "categories": {
            "slow_reply_lead": {
                "triggers": ["تاخر", "يرد", "يردوا", "يردون", "ردو", "بدون رد", "استفسر", "الاستفسار"],
                "desc": "تأخّر الردّ على استفسارات المهتمّين حتى يبردوا",
                "pain": "قد يتأخّر الردّ على المهتمّين، فينصرف أحدهم إلى مكتبٍ آخر قبل أن يصله ردّكم",
                "solution": "ونحن إلى جانب فرقكم نُشغّل أتمتةً تتولّى الردّ الأول خلال أقل من دقيقة، فيبقى المهتمّ معكم",
            },
            "viewing_coord": {
                "triggers": ["معاين", "المعاين", "زياره", "تنسيق"],
                "desc": "صعوبة تنسيق مواعيد المعاينات",
                "pain": "تنسيق مواعيد المعاينات يستهلك وقت فريقكم، وبعضها لا يكتمل",
                "solution": "وبأتمتةٍ تعمل إلى جانبكم يُنسَّق الموعد ويُذكَّر به المهتمّ تلقائياً، فترتفع الزيارات الفعلية",
            },
            "vacancy": {
                "triggers": ["شاغر", "فاضي", "اشغال", "تاجير"],
                "desc": "بقاء الوحدات شاغرة طويلاً",
                "pain": "تبقى بعض الوحدات شاغرةً أطول ممّا ينبغي",
                "solution": "ونحن إلى جانبكم نُشغّل أتمتةً تتابع المهتمّين حتى الإغلاق، فتقصر مدّة الشغور",
            },
            "campaigns": {
                "triggers": ["حمله", "حملات", "تسويق", "قوائم", "صادر"],
                "desc": "قوائم البيع والإيجار دون تواصل صادر منتظم",
                "pain": "قوائمكم للبيع والإيجار تفتقر إلى تواصلٍ صادرٍ وحملاتٍ منتظمة",
                "solution": "وبأتمتةٍ إلى جانب فرقكم يمضي التواصل الصادر والحملات على القوائم معاً من اليوم الأول",
            },
            "rent_collection": {
                "triggers": ["تحصيل", "دفعه", "دفعات", "سداد", "تاخر الايجار"],
                "desc": "تأخّر دفعات الإيجار ومتابعة تحصيلها وإسناد الملّاك",
                "pain": "تتأخّر دفعات الإيجار، وتستهلك متابعة تحصيلها ومساندة الملّاك جهد فريقكم",
                "solution": "ونحن إلى جانبكم نُشغّل أتمتةً تُذكّر المستأجرين بدفعاتهم وتتابع التحصيل وتُسند ملّاككم، دون فريق دعمٍ إضافي",
            },
            "dev_tenders": {
                "triggers": ["مناقص", "تطوير", "اعتماد", "فرصه"],
                "desc": "مناقصات التطوير تمرّ دون فحص وردّ في وقته",
                "pain": "قد تمرّ مناقصات التطوير دون فحصٍ أو ردٍّ جاهزٍ في وقته",
                "solution": "وبأتمتةٍ إلى جانبكم تُفحَص مناقصات اعتماد وفرصة فور نشرها ويُجهَّز الردّ، فلا تفوتكم فرصة",
            },
        },
    },
    "training": {
        "desc": "معهد تدريب: ذروة موسم التسجيل، متابعة المستفسر حتى الحسم، مناقصات التدريب الحكومية (اعتماد وفرصة)",
        "general": {
            "pain": "يُثقل موسم التسجيل فريقكم، ومناقصات التدريب الحكومية لا تنتظر، فيضيع مستفسرٌ أو يفوت موعد تقديم",
            "solution": "ونحن إلى جانب فرقكم نُشغّل أتمتةً تتولّى الردّ على المستفسرين في ذروة الموسم وتفحص كل مناقصةٍ فور نشرها وتجهّز الردّ، بفريقٍ واحدٍ طوال الموسم",
        },
        "categories": {
            "season_overload": {
                "triggers": ["موسم التسجيل", "التسجيل", "زحمه", "زحام", "كثره الاستفسار", "ضغط"],
                "desc": "ذروة موسم التسجيل تفوق طاقة الفريق فتضيع مكالمات ورسائل",
                "pain": "تفوق ذروة موسم التسجيل طاقة فريقكم، فتفوت مكالماتٌ ورسائل",
                "solution": "ونحن إلى جانب فرقكم نُشغّل أتمتةً تستوعب كل مكالمةٍ ورسالة في أعلى مواسم القبول، فلا يضيع مستفسر",
            },
            "incomplete_reg": {
                "triggers": ["لم يكمل", "ما كمل", "يكمل", "تسجيل ناقص", "توقف", "لم يسجل"],
                "desc": "عدم متابعة المستفسر حتى إتمام التسجيل",
                "pain": "يتوقّف بعض المستفسرين في منتصف تسجيلهم فلا يجدون من يتابعهم حتى الحسم",
                "solution": "وبأتمتةٍ إلى جانب فرقكم يُتابَع كل مستفسرٍ ويُذكَّر حتى يُتمّ تسجيله، فترتفع نسبة الإتمام",
            },
            "slow_reply_edu": {
                "triggers": ["تاخر", "يرد", "يردون", "ردو", "بدون رد", "استفسار"],
                "desc": "تأخّر الردّ على استفسارات المتدرّبين",
                "pain": "قد يتأخّر الردّ على استفسارات المتدرّبين حتى ينصرفوا",
                "solution": "ونحن إلى جانب فرقكم نُشغّل أتمتةً تردّ على استفساراتهم فور وصولها، فيجد المستفسر جوابه عندكم",
            },
            "gov_tenders": {
                "triggers": ["مناقص", "حكومي", "اعتماد", "فرصه", "تقديم", "منافسه"],
                "desc": "مناقصات التدريب الحكومية تمرّ أو يتأخّر التقديم عليها",
                "pain": "قد تمرّ مناقصات التدريب الحكومية، أو يصل تقديمكم قريباً من الموعد النهائي",
                "solution": "وبأتمتةٍ إلى جانبكم تُفحَص كل مناقصة تدريبٍ على اعتماد وفرصة فور نشرها ويُجهَّز الردّ قبل الموعد النهائي",
            },
        },
    },
}

_TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")


def _norm(s: str) -> str:
    """Normalize Arabic for matching: strip tashkeel, unify alef/ya/hamza, lowercase latin."""
    s = (s or "").lower()
    s = _TASHKEEL.sub("", s)
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ٱ", "ا")
    s = s.replace("ى", "ي").replace("ئ", "ي").replace("ؤ", "و").replace("ة", "ه")
    s = re.sub(r"[ـ\s]+", " ", s)  # tatweel + collapse whitespace
    return s.strip()


# Arabic clitics/prefixes that hide a trigger from substring matching. Reviews are written
# in dialect and inflect freely — the trigger 'يرد' must still match 'ما ترد', 'ما يردون',
# 'والرد'. Stripping these makes the DETERMINISTIC pass morphology-tolerant, so a working
# LLM key stops being a prerequisite for personalised pain.
# Deliberately CONSERVATIVE. An earlier, looser version (stripping م/س/ا and matching stems
# by two-way containment) raised the match count 2/9 -> 6/9 but most of the new matches were
# WRONG: 'معتمده' (accredited) bled into the 'اعتماد' trigger and sent a support-response
# complaint to gov_tenders. Wrong pain is worse than general pain — it ships confidently
# personalised copy about a problem the lead does not have. Only clitics and the imperfect
# verb prefixes are stripped, and stems must match EXACTLY.
_PREFIXES = ("وال", "بال", "كال", "فال", "لل", "ال", "و", "ب", "ل", "ي", "ت", "ن")
_SUFFIXES = ("ون", "ين", "ات", "ها", "هم", "كم", "نا", "ه")
_MIN_STEM = 3   # never stem below 3 chars — short stems cause false positives ('رد' in 'برد')


def _stem(word: str) -> str:
    """Crude affix-stripper for matching only (never for display)."""
    w = word
    for p in _PREFIXES:
        if w.startswith(p) and len(w) - len(p) >= _MIN_STEM:
            w = w[len(p):]
            break
    for s in _SUFFIXES:
        if w.endswith(s) and len(w) - len(s) >= _MIN_STEM:
            w = w[:-len(s)]
            break
    return w


def _stems(text: str) -> set[str]:
    return {_stem(w) for w in _norm(text).split() if w}


# ── greeting ────────────────────────────────────────────────────────────────
# Lives here, not in outreach.py, because three callers need it and this module is
# stdlib-only: outreach (WhatsApp + local render), snov_push (pushes it as a custom field)
# and snov_preview. Snov templates have no conditionals, so the person-vs-company choice
# has to be made where the data is — here — and shipped as one finished string.

_FEM_SUFFIX = ("ة", "ى", "ا")
_FEM_NAMES = {"سارة", "ساره", "مريم", "نور", "هند", "جواهر", "شهد", "رغد", "لمى", "دعاء",
              "أمل", "امل", "وفاء", "أسماء", "اسماء", "رهف", "غادة", "غاده", "بشرى",
              "ريم", "دانة", "دانه", "منى", "سلمى", "هيا", "لطيفة", "لطيفه", "نوف"}
_ARABIC_RE = re.compile(r"[؀-ۿ]")


def title_for(full_name: str) -> str:
    """`الأستاذة` for a woman, `الأستاذ` otherwise.

    Was hardcoded masculine, so every female contact was addressed as a man in real
    outreach under the operator's name — caught rendering "الأستاذ سارة" on 2026-07-21.
    Arabic gender cannot be inferred reliably from a name in general, so this is
    deliberately conservative: الأستاذة only on a clear feminine marker in the FIRST name,
    otherwise the masculine form rather than a guess. Both errors are rude, which is why a
    lead with no personal name gets the company greeting instead of a coin flip.
    """
    first = (full_name or "").strip().split(" ")[0]
    if not first:
        return "الأستاذ"
    if first in _FEM_NAMES or (len(first) > 2 and first.endswith(_FEM_SUFFIX)):
        return "الأستاذة"
    return "الأستاذ"


RLM = "‏"    # RIGHT-TO-LEFT MARK — a hint only. NOT enough on its own; see below.
RLE = "‫"    # RIGHT-TO-LEFT EMBEDDING — opens a right-to-left run
PDF = "‬"    # POP DIRECTIONAL FORMATTING — closes it


def rtl_plain(text: str) -> str:
    """Force right-to-left rendering of Arabic that will NOT carry HTML.

    Arabic sent as plain text has no direction, so a mail client lays it out left-to-right
    and every trailing comma and full stop wraps to the WRONG end of the line:

        ،السلام عليكم ورحمة الله وبركاته      <- the comma belongs at the other end
        .ساعدنا مكاتبَ عقاريةً أخرى

    Delivered to the operator's inbox looking exactly like that on 2026-07-21. To a native
    reader that is not a subtle flaw; it is the first impression of a cold email.

    **RLM alone does not fix this** — that was the first attempt and it shipped unchanged.
    A RIGHT-TO-LEFT MARK only resolves the direction of NEUTRAL characters next to it; it
    does not set the base direction of the line, so the paragraph stays LTR and the trailing
    punctuation still jumps. Each line has to be wrapped in a directional EMBEDDING —
    RLE … PDF — which does set base direction.

    Needed because `snov.send` html.escape()s its body, so `<div dir="rtl">` cannot survive
    on that path. The controls are zero-width, cost two characters per line, and are
    harmless inside HTML, so this is applied either way rather than guessing which path a
    body takes.
    """
    out = []
    for line in (text or "").split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith(RLE):
            out.append(line)
            continue
        out.append(RLE + line.replace(RLM, "").replace(PDF, "") + PDF)
    return "\n".join(out)


def greeting(contact_name: str = "", company: str = "") -> str:
    """Person when we have a real one, company otherwise. Never empty.

    The name must be ARABIC to be used: transliterating a Latin-script surname into Arabic
    guesses a spelling, and the wrong spelling of someone's own name is worse than not
    using it. Never returning empty matters for the Snov path — these campaigns set
    skip_recipients_without_variables_data=true, so an empty greeting would silently drop
    the recipient rather than mail them.
    """
    name = (contact_name or "").strip()
    if name and _ARABIC_RE.search(name):
        return f"{title_for(name)} {name}"
    company = (company or "").strip()
    return f"القائمون على {company} الكرام" if company else "أهل الشركة الكرام"


CHEAP_MODEL = "qwen/qwen3.6-plus"   # same cheap model the enrichment uses

# The composer WRITES customer-facing Arabic; classify_llm only picks a category id from a
# fixed list. Those are different jobs and they get different models. A cheap model is fine
# at choosing between five labels and not fine at Saudi-dialect B2B copy that goes out under
# the operator's name — and the failure is invisible, because wrong-but-fluent Arabic still
# passes every automated check we have. Same model review_pains uses, for the same reason:
# measured across the pool the difference is cents.
COMPOSE_MODEL_DEFAULT = "qwen/qwen3-235b-a22b"


def compose_model() -> str:
    """Resolved lazily: `_env` is defined further down this module."""
    return _env("COMPOSE_MODEL") or COMPOSE_MODEL_DEFAULT


def classify_llm(vertical: str, pain_line: str, key: str) -> str | None:
    """Semantic fallback: map a pain_line to a category id (or None) via a cheap model.

    Used only when the deterministic keyword pass finds nothing — Arabic morphology makes
    keyword matching miss inflected forms. Returns a category id, or None for 'off-topic /
    not solvable here' (-> general, honouring the relevance rule).
    """
    import json
    import urllib.request
    lib = LIBRARY[vertical]
    cats = "\n".join(f'- {cid}: {c["desc"]}' for cid, c in lib["categories"].items())
    prompt = (
        f"Vertical: {lib['desc']}\n"
        f"A lead's pain (from their own reviews): \"{pain_line}\"\n\n"
        f"Which ONE of these known, solvable pains does it best match?\n{cats}\n\n"
        'Return JSON {"category":"<id>"} for the best match, or {"category":"none"} if it does '
        "not clearly match any (e.g. it praises them, or is off-topic). Do not guess."
    )
    body = json.dumps({"model": CHEAP_MODEL, "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0.0}).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            txt = json.load(r)["choices"][0]["message"]["content"]
        m = re.search(r"\{.*\}", txt, re.S)
        cid = str(json.loads(m.group(0)).get("category", "none")).strip() if m else "none"
        return cid if cid in lib["categories"] else None
    except Exception as e:
        # Signal FAILURE distinctly from "no match". Returning None here would make a dead
        # key or a rate-limit look identical to "this pain isn't solvable" — the caller
        # would then report 'no solvable match -> general' and quietly ship generic copy.
        print(f"    (classify_llm FAILED — semantic pass unavailable: {e})")
        return False


def select(vertical: str, pain_line: str, *, use_llm: bool = False, key: str | None = None) -> dict:
    """Relevance-rank specific vs general and return the winning COUPLED pair + trace."""
    vk = (vertical or "").strip().lower()
    lib = LIBRARY.get(vk)
    if not lib:
        raise ValueError(f"unknown vertical {vertical!r}; known: {list(LIBRARY)}")
    general = lib["general"]
    p_norm = _norm(pain_line)

    def _general(reason: str) -> dict:
        return {"choice": "general", "category": None, "score_specific": 0.0,
                "score_general": GENERAL_RELEVANCE, "reason": reason,
                "pain": general["pain"], "solution": general["solution"]}

    def _specific(cat: str, score: float, reason: str) -> dict:
        # HARD RULE (operator, 2026-07-14): the lead's raw pain_line words NEVER ship —
        # reviews are customer complaints (accusations, first-person venting) and no
        # marker blacklist can catch every phrasing. The pain_line only PICKS the
        # category; the category's neutral, unattributed wording carries the pain.
        return {"choice": "specific", "category": cat, "score_specific": score,
                "score_general": GENERAL_RELEVANCE, "reason": reason,
                "pain": lib["categories"][cat]["pain"],
                "solution": lib["categories"][cat]["solution"]}

    if not p_norm:
        return _general("no specific pain_line -> general (whole)")

    # tier 1 — deterministic fast-path. Two passes, both keyword-grounded:
    #   (a) raw substring on the normalized text (original behaviour, exact phrases)
    #   (b) stem-vs-stem, which catches the inflected dialect forms reviews actually use
    #       ('ما ترد' vs trigger 'يرد') without needing the LLM pass.
    p_stems = _stems(pain_line)
    best_cat, best_hits = None, 0
    for cat, spec in lib["categories"].items():
        hits = 0
        for kw in spec["triggers"]:
            kw_n = _norm(kw)
            if kw_n in p_norm:
                hits += 1
                continue
            kw_stems = {_stem(w) for w in kw_n.split() if w}
            # EXACT stem equality only — no containment in either direction. Multi-word
            # triggers must match every part.
            if kw_stems and kw_stems <= p_stems:
                hits += 1
        if hits > best_hits:
            best_cat, best_hits = cat, hits
    score_specific = best_hits * PER_KEYWORD + (GROUNDED_BONUS if best_hits else 0.0)
    if best_cat and score_specific > GENERAL_RELEVANCE:
        return _specific(best_cat, score_specific, f"keyword: maps to '{best_cat}' ({best_hits} kw) -> beats general")

    # tier 2 — cheap-LLM semantic fallback (morphology-robust)
    #   category id -> matched | None -> genuinely no match | False -> the call FAILED
    if use_llm and key:
        cid = classify_llm(vk, pain_line, key)
        if cid is False:
            return _general("llm: semantic pass FAILED (see error above) -> general; "
                            "this lead was NOT semantically classified")
        if cid:
            return _specific(cid, GENERAL_RELEVANCE + GROUNDED_BONUS, f"llm: semantic match -> '{cid}'")
        return _general("llm: no solvable match -> general more relevant")

    return _general("specific present but no keyword/stem match -> general (enable --llm for semantic pass)")


# ── generated {{2}} ─────────────────────────────────────────────────────────
#
# The library is retrieval: 4-6 blocks per vertical, so a company with several distinct
# problems still receives one pre-written sentence. That ceiling is why every lead sent on
# 2026-07-20 rendered the general block. The generated path writes the pain clause for THIS
# company from the full pain profile `review_pains.pain_profile()` produced.
#
# What keeps it safe is what is NOT in the prompt. The model receives only English pain
# DESCRIPTORS and counts — never a review, never a quote, never a rating. So the copy cannot
# cite a customer's feedback back to them even if the model tried to; the rule is enforced
# by the data flow, not by an instruction the model might ignore.
#
# Relevance is decided HERE, because this is the only layer that knows what we sell: the
# prompt carries the vertical's real solution catalogue and is told to drop any pain we do
# not address. A company whose only problem is pricing gets the vertical's general block,
# not a response-time pitch aimed at a pain it does not have.

# Output that must never ship, checked in code after generation. Each is a real defect that
# has reached or nearly reached a customer.
_BANNED_SUBSTRINGS = (
    "نُؤتمت", "نؤتمت",          # the coined verb the operator rejected
    "—", "–",                    # em/en dash: an AI tell, doctrine forbids it
    "·", "•",
)
# Anything that reveals we read their reviews. The pain may be that specific; saying why
# it is known never ships.
_REVIEW_TELLS = ("تقييم", "التقييمات", "مراجعات", "المراجعات", "تعليقات", "التعليقات",
                 "review", "rating", "لاحظنا أن", "قرأنا", "اطلعنا على")
_MAX_BLOCK_CHARS = 340

# Taa marbuta written as haa. Normal in chat, wrong in formal B2B copy, and invisible to
# every other check here — the model produced the subject "متابعه ضائعه؟" on 2026-07-21.
# A general rule is not possible (many words legitimately end in ه), so this is a list of
# the words this pipeline actually uses, and it is cheap to extend.
_ORTHOGRAPHY = {
    "متابعه": "متابعة", "مكالمه": "مكالمة", "مراجعه": "مراجعة", "استجابه": "استجابة",
    "سرعه": "سرعة", "خدمه": "خدمة", "شركه": "شركة", "مؤسسه": "مؤسسة", "عياده": "عيادة",
    "صيانه": "صيانة", "منافسه": "منافسة", "فرصه": "فرصة", "ضائعه": "ضائعة",
    "متاخره": "متأخرة", "بطيئه": "بطيئة", "مهمله": "مهملة", "منتظمه": "منتظمة",
    # Misplaced hamza — the model wrote "ردود بطيءة؟" on a live run. The hamza sits on the
    # yaa (بطيئة), not standalone before the taa.
    "بطيءة": "بطيئة", "بطيءه": "بطيئة", "ضاءعة": "ضائعة", "فاءتة": "فائتة",
    "متاخرة": "متأخرة", "تاخر": "تأخّر", "مؤجله": "مؤجلة",
}


def _orthography_problems(text: str) -> list[str]:
    """Words spelled with ه where formal Arabic needs ة.

    Strips the definite article and common proclitics before looking a word up: the first
    version missed `المتابعه` because it only matched the bare `متابعه`, and Arabic copy
    carries the article far more often than not.
    """
    # LETTERS only. `[؀-ۿ]` also matches Arabic punctuation — ؟ (U+061F) and ، (U+060C) —
    # so "ضائعه؟" came through as a single token and never matched the dictionary. Every
    # slip at the end of a sentence, which is where they mostly are, was being missed.
    out = []
    for w in set(re.findall(r"[ء-يـً-ْ]+", text or "")):
        bare = re.sub(r"^(وال|فال|بال|كال|لل|ال|و|ف|ب|ك|ل)", "", w)
        for form in (w, bare):
            if form in _ORTHOGRAPHY:
                out.append(f"{w} should be {_ORTHOGRAPHY[form]}")
                break
    return sorted(out)


def _catalogue(lib: dict) -> str:
    """The vertical's solvable pains and their exact solutions, as the model's menu."""
    rows = [f'  - {c["pain"]}  ->  {c["solution"]}' for c in lib["categories"].values()]
    rows.append(f'  - (general) {lib["general"]["pain"]}  ->  {lib["general"]["solution"]}')
    return "\n".join(rows)


def validate_block(block: str) -> list[str]:
    """Why this generated block must not ship. Empty list = acceptable."""
    problems = []
    text = (block or "").strip()
    if not text:
        return ["empty"]
    if len(text) > _MAX_BLOCK_CHARS:
        problems.append(f"too long ({len(text)} > {_MAX_BLOCK_CHARS})")
    for bad in _BANNED_SUBSTRINGS:
        if bad in text:
            problems.append(f"contains banned {bad!r}")
    low = text.lower()
    for tell in _REVIEW_TELLS:
        if tell.lower() in low:
            problems.append(f"reveals review knowledge ({tell!r})")
    if "," in text:
        problems.append("Latin comma — Arabic copy uses ،")
    # Scaffolding that survived a tolerant parse. Reachable when the model emits Arabic
    # containing unescaped quotes: json.loads fails, the bare-text path returns the whole
    # `{"block":"..."}` wrapper, and every other check here passes because the payload IS
    # Arabic. Without this the wrapper would ship as the message.
    if any(t in text for t in ("{", "}", "<block>", "</block>", '"block"')):
        problems.append("contains raw scaffolding, not clean copy")
    # No Latin words, full stop. Verified against all 29 library blocks: not one contains a
    # run of Latin letters, so this cannot reject good copy — and it catches every shape of
    # leaked scaffolding at once. A model emitted the malformed `[block>` on 2026-07-21,
    # which slipped past a tag-specific check and would have shipped with the copy, along
    # with the trailing solution id. It also catches "review"/"rating" tells for free.
    if (latin := re.search(r"[A-Za-z]{3,}", text)):
        problems.append(f"contains Latin text {latin.group(0)!r} — leaked scaffolding?")
    if not re.search(r"[؀-ۿ]", text):
        problems.append("not Arabic")
    problems += _orthography_problems(text)
    return problems


def _extract(txt: str) -> tuple[str, list[str]]:
    """Pull the block and the claimed solution ids out of whatever shape the reply took.

    Three tolerances, in order, because a usable Arabic sentence must not be thrown away
    over packaging. Tags first (asked for, and unbreakable by quotation marks in the copy),
    then JSON (models default to it regardless of instructions), then the bare reply.
    Both stricter forms failed on real replies on 2026-07-21 and discarded good copy.
    """
    import json

    used: list[str] = []
    if (mu := re.search(r"<used>(.*?)</used>", txt, re.S)):
        used = [u.strip() for u in mu.group(1).split(",") if u.strip()]

    if (mb := re.search(r"<block>(.*?)</block>", txt, re.S)):
        return mb.group(1).strip(), used

    if (mj := re.search(r"\{.*\}", txt, re.S)):
        try:
            obj = json.loads(mj.group(0))
            if isinstance(obj, dict) and obj.get("block"):
                raw_used = obj.get("used") or []
                if isinstance(raw_used, str):
                    raw_used = [u.strip() for u in raw_used.split(",") if u.strip()]
                return str(obj["block"]).strip(), used or list(raw_used)
        except json.JSONDecodeError:
            pass    # unescaped quotes in Arabic copy — fall through to the bare text

    # A JSON object whose Arabic contains an unescaped quote: json.loads already failed
    # above, and the bare path would otherwise return the whole `{"block":"…"}` wrapper as
    # copy. Pull the value out positionally instead — first quote after the key, last quote
    # before the closing brace. Seen repeatedly on live replies; without this the run falls
    # back to the library and the lead silently loses its personalised block.
    if (mk := re.search(r'"block"\s*:\s*"', txt, re.I)):
        rest = txt[mk.end():]
        # The value ends at the quote that closes it — the one followed by the NEXT key or
        # by the closing brace. Not the last quote in the string: a trailing `"used":"…"`
        # would otherwise be swallowed into the copy, which is exactly what happened first
        # time. Prefer the next-key boundary, fall back to the final brace.
        nxt = re.search(r'"\s*,\s*"[A-Za-z_]+"\s*:', rest)
        end = nxt.start() if nxt else rest.rfind('"')
        if end > 0:
            return rest[:end].strip(), used

    # Bare reply: strip any stray tag/label scaffolding and take what is left.
    bare = re.sub(r"```[a-zA-Z]*", " ", txt)                    # markdown fences
    bare = re.sub(r"</?(block|used)>", " ", bare)
    bare = re.sub(r"^\s*(block|copy|sentence)\s*[:：]\s*", "", bare.strip(), flags=re.I)
    bare = bare.strip().strip('"').strip()

    # Last resort: keep the longest ARABIC run and discard everything else. The copy is
    # Arabic and the scaffolding never is, so this survives every wrapper shape the model
    # has produced — unescaped-quote JSON, half-closed tags, a stray "Block:" label — where
    # the specific parsers above kept missing one variant and falling back to the library on
    # a third of runs. Only used when the text still carries Latin scaffolding, so a clean
    # bare reply is returned untouched.
    if re.search(r"[A-Za-z]{3,}|[{}]", bare):
        runs = re.findall(r"[؀-ۿ][؀-ۿ\s،؛.؟!%0-9ً-ْ]*", bare)
        if runs:
            longest = max(runs, key=len).strip()
            if len(longest) > 40:          # a real sentence, not a stray word
                return longest, used
    return bare, used


def generate_block(vertical: str, pain_summary: str, pains: list[dict] | None,
                   key: str, company: str = "") -> tuple[str | None, dict]:
    """Write `{{2}}` for THIS company: their real pains, matched only to what we solve."""
    import json                    # local, matching classify_llm — this module is
    import urllib.request          # stdlib-only and imports must stay cheap
    vk = (vertical or "").strip().lower()
    lib = LIBRARY.get(vk)
    if not lib:
        raise ValueError(f"unknown vertical {vertical!r}; known: {list(LIBRARY)}")

    listed = "\n".join(f"  - {p['pain'].replace('_', ' ')} "
                       f"(reported by {p['count']} of {p['reviewed']})"
                       for p in (pains or []))
    prompt = (
        f"You write Arabic B2B outreach for NAVAIA, which builds automation for Saudi "
        f"companies. Write the ONE sentence that names a prospect's operational problem and "
        f"the automation we run for it.\n\n"
        f"Prospect sector: {lib['desc']}\n"
        + (f"Their operational situation: {pain_summary}\n" if pain_summary else "")
        + (f"Problems identified, most common first:\n{listed}\n" if listed else "")
        + f"\nNAVAIA only solves these, with these exact solutions:\n{_catalogue(lib)}\n\n"
        f"Rules:\n"
        f"1. Use ONLY problems from the prospect's situation that CLEARLY match our "
        f"solvable list. IGNORE any problem we do not solve (pricing, fees, rent increases, "
        f"refunds, deposits, legal disputes, staff behaviour, quality of the work, "
        f"maintenance faults). Never promise anything outside the list, and never stretch "
        f"one of their problems to fit a solution — a fee complaint is NOT a collection "
        f"problem, and a maintenance fault is NOT a response-time problem. When in doubt, "
        f"treat it as not solvable and follow rule 3.\n"
        f"2. If two or three of their problems are solvable, cover them together in one "
        f"flowing sentence. Do not list more than three.\n"
        f"3. If NONE of their problems are solvable by us, or you were given nothing "
        f"useful, write the sector's general pain and its solution instead. Never invent a "
        f"problem and never leave it vague.\n"
        f"4. State the problem as a known, fixable situation in their line of work. NEVER "
        f"say or imply that anyone told us, that we read anything about them, or that "
        f"customers complained. Do not mention reviews, ratings or feedback.\n"
        f"5. Modern Standard Arabic. Arabic commas (،) only, never Latin commas. No "
        f"em-dashes, no bullets, no marketing slogans, no exclamation marks.\n"
        f"6. Never use the invented verb 'نُؤتمت'. Use 'تتولّى' or 'تُشغّل'.\n"
        f"7. Address them as 'كم' (plural, respectful). Do not name the company.\n"
        f"8. Numerals 11-99 take a singular noun.\n"
        f"9. Shape: the problem، then our automation for it. One sentence, max 45 words.\n\n"
        # NOT JSON. Arabic copy legitimately contains quotation marks and the model emitted
        # an unescaped one on 2026-07-21, so json.loads failed and a perfectly good sentence
        # was thrown away. Tags cannot be broken by the content they wrap.
        f"Reply with the sentence between <block></block> tags, then the ids of the "
        f"solvable pains you used between <used></used> tags, comma separated.\n"
        f"Use ONLY these ids: {', '.join(lib['categories'])}, general\n"
        f"Example: <block>...</block><used>slow_reply,general</used>"
    )

    body = json.dumps({"model": compose_model(), "temperature": 0.3,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            txt = json.load(r)["choices"][0]["message"]["content"]
    except Exception as e:  # noqa: BLE001
        # A failure must never silently become "no pain" — the caller falls back to the
        # library and SAYS it did, so a dead key cannot quietly flatten every lead.
        return None, {"generated": False, "reason": f"generation FAILED: {e}"}

    block, used = _extract(txt)

    # Structural check that the model stayed inside the catalogue. It cannot prove the
    # MAPPING is sound — a fee complaint bent into "rent collection" would still pass — but
    # it does prove no solution was invented, and it surfaces the mapping in the trace so a
    # human sees which promise is being made before the gate.
    known = set(lib["categories"]) | {"general"}
    invented = [u for u in used if u and u not in known]
    if invented:
        return None, {"generated": False,
                      "reason": f"rejected: promised solutions we do not have: {invented}",
                      "rejected_text": block}

    problems = validate_block(block)
    if problems:
        return None, {"generated": False, "reason": f"rejected: {'; '.join(problems)}",
                      "rejected_text": block}
    return block, {"generated": True, "reason": "generated from the lead's own pain profile",
                   "pains_seen": [p["pain"] for p in (pains or [])],
                   "solutions_used": used}


# The vertical's approved subject, used as the FLOOR when generation is off, fails, or is
# rejected. Verbatim from workforce/04_outreach_templates.md.
SUBJECT_FALLBACK = {
    "realestate": "مهتمّ يبرد؟",
    "contracting": "عقود تفوتكم؟",
    "training": "موسمٌ يُغرقكم؟",
    "clinics": "مواعيد فائتة؟",
    "finance": "تحصيلٌ أعلى؟",
}
_MAX_SUBJECT_CHARS = 60


def validate_subject(subject: str) -> list[str]:
    """Why this generated subject must not ship. Empty list = acceptable.

    Stricter than the body on length and shape: a subject is the one line that decides
    whether the mail is opened, and a long or odd one reads as spam before it is read at all.
    """
    problems = []
    text = (subject or "").strip()
    if not text:
        return ["empty"]
    if len(text) > _MAX_SUBJECT_CHARS:
        problems.append(f"too long ({len(text)} > {_MAX_SUBJECT_CHARS})")
    if "\n" in text:
        problems.append("multi-line")
    for bad in _BANNED_SUBSTRINGS:
        if bad in text:
            problems.append(f"contains banned {bad!r}")
    low = text.lower()
    for tell in _REVIEW_TELLS:
        if tell.lower() in low:
            problems.append(f"reveals review knowledge ({tell!r})")
    if re.search(r"[A-Za-z]{3,}", text):
        problems.append("contains Latin text — leaked scaffolding?")
    if not re.search(r"[؀-ۿ]", text):
        problems.append("not Arabic")
    # A cold subject that shouts is a spam signal before anyone reads a word of it.
    if "!" in text or "؟؟" in text or text.isupper():
        problems.append("shouty punctuation")
    # ONE question, not a stack of them. The model produced "ردود متأخّرة؟ متابعات ضائعة؟"
    # on 2026-07-21 — two questions in six words reads as clickbait, and stacking hooks is a
    # spam-filter pattern. A subject asks one thing.
    if text.count("؟") + text.count("?") > 1:
        problems.append("more than one question — subject asks ONE thing")
    problems += _orthography_problems(text)
    return problems


def generate_subject(vertical: str, pains: list[dict] | None, key: str,
                     pain_summary: str = "") -> tuple[str, dict]:
    """A short Arabic subject for THIS lead, or the vertical's approved one as the floor.

    Same containment as the body: the model sees English pain DESCRIPTORS and counts, never
    a review, quote or rating, so the subject cannot cite a customer's feedback back to them.
    Falls back rather than shipping anything that fails validation — the fallback is approved
    copy, so falling back costs nothing.
    """
    import json
    import urllib.request

    vk = (vertical or "").strip().lower()
    floor = SUBJECT_FALLBACK.get(vk, "")
    lib = LIBRARY.get(vk)
    if not lib or not key or not (pains or pain_summary):
        return floor, {"generated": False, "reason": "no profile or no key — approved floor"}

    listed = ", ".join(p["pain"].replace("_", " ") for p in (pains or [])[:4])
    prompt = (
        f"Write ONE Arabic email subject line for a cold B2B email to a Saudi company.\n\n"
        f"Sector: {lib['desc']}\n"
        + (f"Their operational problems: {listed}\n" if listed else "")
        + (f"Context: {pain_summary}\n" if pain_summary else "")
        + f"\nRules:\n"
        f"1. MAXIMUM 6 words. Short is the whole point.\n"
        f"2. Name the problem from their side, as a question or a short statement. "
        f'Examples of the right register: "مهتمّ يبرد؟", "عقود تفوتكم؟".\n'
        f"3. Use ONLY a problem we solve (slow replies, lost follow-up, missed enquiries, "
        f"unanswered calls). If none of theirs qualify, describe the sector's usual one.\n"
        f"4. NEVER mention reviews, ratings, feedback, or that anyone told us anything.\n"
        f"5. No company name, no exclamation marks, no emoji, no Latin letters, no "
        f"em-dashes. Arabic commas only.\n"
        f"6. Do not sell, do not greet, do not use our company name.\n\n"
        f"Reply with the subject between <s></s> tags. Example: <s>مهتمّ يبرد؟</s>"
    )
    body = json.dumps({"model": compose_model(), "temperature": 0.4,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            txt = json.load(r)["choices"][0]["message"]["content"]
    except Exception as e:  # noqa: BLE001
        return floor, {"generated": False, "reason": f"subject generation FAILED: {e}"}

    m = re.search(r"<s>(.*?)</s>", txt, re.S)
    subject = (m.group(1) if m else txt).strip().strip('"').strip()
    problems = validate_subject(subject)
    if problems:
        return floor, {"generated": False,
                       "reason": f"subject rejected: {'; '.join(problems)}",
                       "rejected_text": subject}
    return subject, {"generated": True, "reason": "generated from the lead's pain profile"}


def compose_block(vertical: str, pain_line: str, *, use_llm: bool = False,
                  key: str | None = None, pain_summary: str = "",
                  pains: list[dict] | None = None) -> tuple[str, dict]:
    """Return the `{{2}}` block (coupled pain->solution) + the decision trace.

    Generates when a pain profile and a key are available; otherwise falls back to the
    library. The fallback is not a failure mode — it is the floor, and it is why an empty
    or unusable pain profile still yields publishable copy.
    """
    if key and (pain_summary or pains):
        block, meta = generate_block(vertical, pain_summary, pains, key,
                                     company="")
        if block:
            block = block.replace(" — ", "، ").replace("—", "،").rstrip()
            # The library blocks end in a full stop; a generated one often did not, so it ran
            # into the following paragraph. Cosmetic in isolation, visible in a real email.
            if block and block[-1] not in ".!؟":
                block += "."
            meta.update({"choice": "generated", "category": None,
                         "score_specific": 0.0, "score_general": GENERAL_RELEVANCE})
            return block, meta
        print(f"    compose: {meta.get('reason')} -> falling back to the library")

    d = select(vertical, pain_line, use_llm=use_llm, key=key)
    pain = d["pain"].rstrip("،.").strip()
    solution = d["solution"].strip()
    block = f"{pain}، {solution}."
    # Doctrine: no AI tells — an em-dash must never ship, wherever it snuck in.
    block = block.replace(" — ", "، ").replace("— ", "").replace(" —", "").replace("—", "،")
    d["generated"] = False
    return block, d


# ── self-test ──────────────────────────────────────────────────────────────
_SELFTEST = [
    ("clinics", "", "empty -> general"),
    ("clinics", "لاحظت أن بعض مراجعيكم ذكروا تأخّر الردّ على اتصالاتهم", "slow_reply -> specific"),
    ("clinics", "مراجعون يشتكون أنهم لا يجدون رداً بعد الدوام", "after_hours -> specific"),
    ("clinics", "الموقع نظيف والطاقم لطيف جداً", "irrelevant/novel -> general wins"),
    ("finance", "عملاء ينسون مواعيد أقساطهم ولا أحد يذكّرهم", "reminder -> specific"),
    ("realestate", "استفسرت عن شقة ولم يردوا عليّ إطلاقاً", "slow_reply_lead -> specific"),
    ("training", "في موسم التسجيل الزحمة كبيرة ولا يردون", "season_overload -> specific"),
]


def _self_test(*, use_llm: bool = False, key: str | None = None) -> None:
    for vertical, pain, note in _SELFTEST:
        block, d = compose_block(vertical, pain, use_llm=use_llm, key=key)
        print(f"[{vertical}] {note}")
        print(f"  pain_line: {pain or '(empty)'}")
        print(f"  -> choice={d['choice']} cat={d['category']} "
              f"score(spec={d['score_specific']:.2f} vs gen={d['score_general']:.2f}) | {d['reason']}")
        print(f"  {{{{2}}}} = {block}\n")


def _env(key: str) -> str | None:
    import os
    v = os.environ.get(key)
    if v:
        return v
    try:
        import os as _os
        p = _os.path.join(_os.path.dirname(__file__), "..", ".env")
        m = re.search(rf"^{re.escape(key)}=(.+)$", open(p, encoding="utf-8").read(), re.M)
        return m.group(1).strip() if m else None
    except OSError:
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--in", dest="inp", help="leads CSV (needs pain_line + a vertical)")
    ap.add_argument("--vertical", help="force a vertical for all rows (else read row['vertical'])")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--llm", action="store_true", help="enable the cheap-LLM semantic fallback")
    args = ap.parse_args()

    # One key name only. This used to read MY_OPENROUTER_KEY first, which went dead on
    # 2026-07-21 — so --llm silently produced library copy instead of generated copy.
    # nav_env.openrouter_key() is the canonical accessor; this module keeps its own _env to
    # stay import-light, so the name is repeated here rather than the fallback logic.
    key = _env("OPENROUTER_API_KEY") if args.llm else None

    if args.self_test or not args.inp:
        _self_test(use_llm=args.llm, key=key)
        return

    # CSV uses `sector`; map it to a library vertical key.
    sector_map = {
        "private clinics": "clinics", "contracting & facilities": "contracting",
        "finance & debt collection": "finance", "real estate": "realestate",
        "training institutes": "training",
    }

    with open(args.inp, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    todo = rows[: args.limit] if args.limit else rows
    n_spec = 0
    for r in todo:
        vertical = (args.vertical or r.get("vertical")
                    or sector_map.get((r.get("sector", "") or "").strip().lower(), ""))
        name = r.get("company_name") or r.get("name", "")
        block, d = compose_block(vertical, r.get("pain_line", ""), use_llm=args.llm, key=key)
        n_spec += d["choice"] == "specific"
        print(f"{name} [{vertical}] -> {d['choice']}"
              + (f"/{d['category']}" if d["choice"] == "specific" else "") )
        print(f"  {{{{2}}}} = {block}")
    print(f"\n{n_spec}/{len(todo)} used a specific coupled pain; the rest used the general default.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""OUTREACH — the script-authority pipeline. One command, scripts decide everything.

Born from the 2026-07-14 postmortem (workforce/POSTMORTEM_2026-07-14.md): every failure
that day came from putting an LLM in charge of deterministic steps. This script keeps
FULL AUTHORITY locally and uses the cloud for exactly ONE thing — the physical send by
Tariq, because the Meta/WhatsApp token lives only in the cloud env. Structural guarantees:

  - RENDERING IS LOCAL AND DETERMINISTIC (templates verbatim + lina_compose token logic).
    No cloud render → no waiting states, no clarification loops, no ~18k output-cap
    truncation, no improvised subjects. What you approve is BYTE-EXACT what is sent.
  - APPROVAL IS LOCAL AND FAST: compact per-lead summary in the terminal + the full
    render written to outreach_render.md for reading; approve all / skip by number.
  - THE CLOUD TASK IS A LITERAL EXECUTION CHECKLIST (exact per-lead payloads, exact
    API shapes, no judgment, no gate, ends [DONE]). This pattern sent 30/30 on 07-14.
  - CRM STATUS UPDATES RUN LOCALLY afterwards (direct crm.navaia.sa PATCH) — the
    in-task CRM tool is flaky per-run and is not trusted with anything.

Usage:
    .venv/Scripts/python.exe scripts/outreach.py                    # all verticals
    .venv/Scripts/python.exe scripts/outreach.py --verticals "Real Estate,Training Institutes"
    .venv/Scripts/python.exe scripts/outreach.py --dry-run          # render + review only
    .venv/Scripts/python.exe scripts/outreach.py --self-test        # fake leads, no CRM/cloud
    .venv/Scripts/python.exe scripts/outreach.py --yes              # unattended: approve all

NEVER pipe stdin at this script to auto-answer its prompts (`printf '\\n' | …`). Use --yes.
Both gates guard an irreversible send and now fail CLOSED on an unanswerable prompt, so
piping gets you an abort at best; before 2026-07-19 the key guard failed OPEN and piping
submitted 153 sends against a $0.91 balance.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
from datetime import datetime

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx

import nav_env
import lina_compose
import site_facts
import pipeline_prep as prep
from navaia_forge import NavaiaForgeClient
from submit_lead_batch import ALL_VERTICALS, resolve_agent

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RENDER_FILE = os.path.join(ROOT, "outreach_render.md")
CAL = "https://cal.com/abdulmajeed-alwardi"
SIG = "عبدالمجيد الوردي"
CRM_BASE = nav_env.crm_base()

# CRM sector -> lina_compose LIBRARY key
# ACTIVE verticals only — locked to three by operator decision 2026-07-19.
# Retired keys (clinics, finance) are deliberately absent: a CRM lead in a retired
# sector finds no key here and is skipped rather than rendered.
VKEY = {
    "Contracting & Facilities": "contracting",
    "Real Estate": "realestate",
    "Training Institutes": "training",
}

# Per-vertical EMAIL ATTACHMENT — the executive summary for that vertical's agent team.
#
# READ THIS BEFORE WIRING IT INTO A SEND. Snov cannot attach a file from here: the workforce's
# Snov integration exposes enrich/verify ONLY (no campaign or send functions), and Snov itself
# has no ad-hoc send endpoint — /v1/send-email and /v1/campaigns/send both 404, probed live
# (workforce/INTEGRATION_CAPABILITIES_AND_GAPS.md). Snov sends only through drip campaigns
# configured in its DASHBOARD, and that is also the only place a file can be attached (6 MB
# total per campaign; each file below is well under). So this mapping is the single source of
# truth for WHICH pdf belongs to WHICH vertical — the upload itself is a manual dashboard step,
# one campaign per vertical. Do not add an --attach flag that silently does nothing.
#
# Paths resolve under NAVAIA_ATTACHMENTS_DIR (default: assets/attachments next to the repo), so
# nothing here hardcodes a laptop path and the same config works in a container.
ATTACHMENT = {
    "Real Estate": "نڤايا — ملخّص تنفيذي · فريق المبيعات العقاري الذكي.pdf",
    "Contracting & Facilities": "نڤايا — ملخّص تنفيذي · فريق المناقصات والمبيعات الذكي.pdf",
    "Training Institutes": "نڤايا — ملخّص تنفيذي · فريق المناقصات ونجاح العملاء.pdf",
}


def attachment_path(vertical: str) -> str:
    """Absolute path to a vertical's PDF, or '' if it is not configured or not on disk.

    Fails closed and SILENT-FREE: callers must treat '' as "no attachment available" and say so
    rather than sending a mail that promises an attachment it does not carry.
    """
    name = ATTACHMENT.get(vertical)
    if not name:
        return ""
    default = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "attachments")
    root = nav_env.env("NAVAIA_ATTACHMENTS_DIR", default) or default
    path = os.path.abspath(os.path.join(root, name))
    return path if os.path.isfile(path) else ""


# Per-vertical trigger sentence for the email {trigger_line} token — the approved,
# unattributed general-pain line (doctrine: never cite reviews; Arabic commas; no em-dash).
TRIGGER = {
    "Contracting & Facilities": "في مثل عملكم قد يتأخّر الردّ على العروض والعطاءات في أوقات الذروة، فتفوتكم فرص.",
    "Real Estate": "في مثل عملكم قد يتأخّر الردّ على الاتصالات والرسائل في أوقات الذروة، فيبرد المهتمّ.",
    "Training Institutes": "في مواسم التسجيل قد يتأخّر الردّ على الاستفسارات، فيضيع مستفسرون مهتمّون.",
    "Private Clinics": "في مثل عملكم قد تفوت مكالمات المراجعين بعد الإغلاق أو في أوقات الذروة.",
    "Finance & Debt Collection": "بين متابعة الأقساط المتأخّرة وتذكير العملاء، قد يتقادم بعض الديون.",
}

# Email {lina_pain} must be a NOUN PHRASE (it follows "تعاني من …"); the library's general
# pains are full sentences, so generals use these instead (the approved email wording).
EMAIL_PAIN = {
    "Contracting & Facilities": "تأخر متابعة العطاءات والعروض",
    "Real Estate": "تأخّر الردّ على المهتمّين والمتابعة",
    "Training Institutes": "تأخّر الردّ على المستفسرين في موسم التسجيل",
    "Private Clinics": "المكالمات الفائتة والإلغاءات دون تذكير",
    "Finance & Debt Collection": "تقادم الديون بسبب تأخّر المتابعة",
}

# Company-name suffixes that are trimmed to get the short form used in {{1}}.
_TAIL = re.compile(
    r"\s*(للمقاولات( العامة)?|للخدمات العقارية|العقارية|لإدارة (المرافق|الأملاك|العقارات)|"
    r"للتجارة والمقاولات( العامة)?( المحدودة)?|للتدريب|العالي للتدريب|المحدودة|"
    r"Training (Institute|Centre|Center|Academy)|Institute|L\.?L\.?C\.?|Co\.?|Company|Group)\s*$",
    re.I)


_ARABIC = re.compile(r"[؀-ۿ]")

# The greeting (person vs company, and the gendered honorific) lives in lina_compose so the
# WhatsApp path, the Snov push and the preview all render the identical string.


def short_name(company: str) -> str:
    """Trim a Maps listing title down to what a person would actually be called.

    Listing titles carry junk that reads badly inside 'القائمون على … الكرام':
    a branch parenthetical ('… (الرياض - حي اشبيليا)') and bilingual names joined by a
    dash ('EXAMPLE Facilities Management Company - المثال لادارة المرافق'). Both shipped
    verbatim into the honorific before this fix.
    """
    s = company.strip()

    # 1. Drop parentheticals ANYWHERE — a listing title carries them mid-string too
    #    ("شركة المثال ... ( مكتب عقار ) ..."), not only at the end. Name invented — this
    #    file ships to a PUBLIC repo, so never paste a real listing title here.
    s = re.sub(r"\s*[\(（][^)）]*[\)）]\s*", " ", s).strip()

    # 1b. Underscores are Google-Maps keyword-salad ("… بيع _تأجير _ادارة املاك"): a real
    #     company name never contains one. Cut from the first underscore-run onward.
    if "_" in s:
        s = s.split("_")[0].strip()
    # 1c. …then peel any trailing standalone service words the salad left behind
    #     ("… العقارية بيع" -> "… العقارية"). A separate word only, never a name fragment.
    for _ in range(4):
        s2 = re.sub(r"\s(بيع|شراء|تأجير|إيجار|ايجار|إدارة|ادارة|أملاك|املاك|عقارات|تسويق|صيانة)\s*$",
                    "", s).strip()
        if s2 == s or len(s2) < 3:
            break
        s = s2

    # 2. Bilingual "English - Arabic" (or the reverse): keep the Arabic side, since the
    #    whole message is Arabic. Only when exactly one side is Arabic, so we never split
    #    a legitimately hyphenated name.
    for sep in (" - ", " – ", " — ", " | ", " / "):
        if sep in s:
            left, _, right = s.partition(sep)
            l_ar, r_ar = bool(_ARABIC.search(left)), bool(_ARABIC.search(right))
            if l_ar != r_ar:
                s = (left if l_ar else right).strip()
            break

    # 3. Peel trailing legal/descriptive suffixes ("للمقاولات العامة", "المحدودة", …).
    for _ in range(3):
        s2 = _TAIL.sub("", s).strip(" -–—|،,")
        if s2 == s or len(s2) < 3:
            break
        s = s2
    return s or company.strip()


def _email_subject_and_body(vertical: str) -> tuple[str, str]:
    """Split the verbatim email template into (primary subject, body with tokens)."""
    tpl = prep.email_touch1_templates()[vertical]
    lines = tpl.splitlines()
    subject = ""
    body_start = 0
    for i, line in enumerate(lines):
        m = re.match(r"\*\*الموضوع:\*\*\s*(.+)", line.strip())
        if m:
            subject = re.split(r"\s*\*\(alt", m.group(1))[0].strip().strip("`*")
            body_start = i + 1
            break
    body = "\n".join(lines[body_start:]).strip()
    return subject, body


_site_facts_cache: dict | None = None


def site_opener(lead: dict) -> tuple[str, str]:
    """(arabic_opener, fact_key) built from the lead's OWN website, or ('','') if none.

    Reads the facts stored by enrich_company_size.py during the sizing crawl — those pages
    were already fetched and previously discarded. A lead that was never crawled, or whose
    site published nothing concrete, simply gets the generic vertical line.
    """
    global _site_facts_cache
    if _site_facts_cache is None:
        try:
            from enrich_company_size import load_cache
            _site_facts_cache = load_cache()
        except Exception:
            _site_facts_cache = {}
    entry = _site_facts_cache.get(lead.get("person_id") or "") or {}
    return site_facts.opener(entry.get("site_facts") or {})


def render_lead(lead: dict, use_llm: bool, or_key: str | None) -> dict:
    """Deterministic render for one lead: WA vars + preview, email subject/body."""
    vertical = lead["sector"]
    vkey = VKEY[vertical]
    company = lead["company"]
    # A name only personalises the greeting if it is written in the language of the letter.
    # Snov returns Latin transliterations, and a Latin name inside an otherwise Arabic
    # message reads worse than no name at all — it looks
    # like a mail-merge failure to the exact executive we are trying to impress. So a
    # non-Arabic contact name falls back to the collective honorific until someone writes
    # the Arabic form into the CRM. We never transliterate it ourselves: a surname can map
    # to several plausible Arabic spellings, and picking the wrong one is worse than
    # being generic.
    contact = (lead.get("contact_name") or "").strip()
    use_name = bool(contact) and bool(_ARABIC.search(contact))
    # One source of truth for the greeting, shared with the Snov path — see
    # lina_compose.greeting. Person when we have an Arabic name, company otherwise.
    honorific = lina_compose.greeting(contact if use_name else "", short_name(company))
    pain_line = lead.get("pain_line") or lead.get("pain_hints") or ""
    # `{{2}}` is GENERATED from the lead's full pain profile when discovery produced one,
    # and falls back to the library block when it did not. The generated path receives only
    # English pain descriptors and counts - never a review, quote or rating - so the copy
    # cannot cite a customer's feedback back to them. Both paths are still rendered locally
    # and still stop at the approval gate; nothing here sends.
    block, meta = lina_compose.compose_block(
        vkey, pain_line, use_llm=use_llm, key=or_key,
        pain_summary=lead.get("pain_summary") or "", pains=lead.get("pains") or None)

    wa = prep.wa_templates()[vertical]
    # {{3}} is the business name in the body — it must be the CLEAN name too, not the raw
    # listing title (the message showed the raw "… ( مكتب عقار ) بيع _تأجير _ادارة املاك").
    wa_vars = [honorific, block, short_name(company), CAL, SIG]
    preview = wa["body"]
    for i, v in enumerate(wa_vars, 1):
        preview = preview.replace("{{%d}}" % i, v)

    email_subject = email_body = None
    # Fail closed on a recipient that is not the lead's own mailbox. On 2026-07-21 a lead
    # whose "website" was an aqar.fm profile page had the PORTAL's info@ enriched onto its
    # CRM record, and this function happily rendered a letter addressed to the lead and
    # handed it to the portal. The address is shown in the approval table, and a human
    # read it and approved anyway — recipient correctness is not something a human
    # eyeballing 20 rows of Arabic will catch, so it has to be checked here.
    email_block = (lead.get("email") or "").strip()
    if email_block and not prep.email_belongs_to(email_block, lead.get("website") or ""):
        print(f"  DROPPED email for {company[:40]}: {email_block} is a third party's "
              f"mailbox (website {lead.get('website') or '-'}) — WhatsApp unaffected")
        email_block = ""
    elif email_block and prep.email_domain_mismatch(email_block, lead.get("website") or ""):
        # Not suppressed: a second private domain is normal. Printed so the operator can
        # spot the case where it is not.
        print(f"  note: {company[:40]} mails from {email_block.rsplit('@', 1)[-1]} but "
              f"its site is {lead.get('website')} — plausible, worth a glance")
    if email_block:
        email_subject, body = _email_subject_and_body(vertical)
        # noun-phrase pain: the matched category's pain fits "تعاني من …"; generals don't.
        # Same defect as the render label: meta has no 'source' key, so the old
        # meta.get("source") was always None and this ALWAYS took the generic branch —
        # the email body was never personalised even when a category matched.
        pain_phrase = (meta["pain"] if meta.get("category")
                       else EMAIL_PAIN[vertical])
        # {trigger_line} is the generic per-vertical sentence every lead in that vertical
        # gets. When the company published something concrete about its own scale, lead
        # with THAT instead: it is specific, true, sourced from their own site, and it sets
        # up the same pain. Falls back to the generic line whenever no fact was found —
        # never invents one. See site_facts.py for why review-mined pain was insufficient.
        opener, opener_key = site_opener(lead)
        fills = {
            "{honorific+name}": honorific,
            "{inbound_context}": "",
            "{trigger_line}": opener or TRIGGER[vertical],
            "{lina_pain}": pain_phrase,
            "{اسم الشركة}": company, "{اسم العيادة}": company, "{اسم المعهد}": company,
        }
        for k, v in fills.items():
            body = body.replace(k, v)
        # Belt and braces on direction. The div below is correct when the HTML survives,
        # but `snov.send` html.escape()s its body — on that path the tags become visible
        # text and the dir attribute does nothing, which is how Arabic reached the
        # operator's inbox laid out left-to-right on 2026-07-21. The RLM is invisible,
        # survives escaping, and fixes the direction on its own.
        body = lina_compose.rtl_plain(body.strip())
        formatted_body = body.replace("\n", "<br>")
        email_body = (
            f'<div dir="rtl" style="text-align: right; direction: rtl; font-family: Arial, sans-serif; font-size: 11pt; line-height: 1.6;">'
            f'{formatted_body}'
            f'</div>'
        )

    phone = re.sub(r"\D", "", lead.get("phone") or "")
    if phone.startswith("0"):
        phone = phone[1:]
    if phone and not phone.startswith("966"):
        phone = "966" + phone

    return {**lead, "wa_template": wa["name"], "wa_vars": wa_vars, "wa_preview": preview,
            # Carried for the Snov campaign path (`--email-via snov`), which pushes these as
            # prospect custom fields the campaign template renders. Without them
            # snov_push.add_prospect REFUSES every lead ("no pain_block") — it will not mail
            # a message with a hole in it — so the whole email channel silently enrols
            # nobody. `block` is the same string {{2}} uses, so WhatsApp and email cannot
            # disagree about this lead's pain.
            "pain_block": block,
            # Overrides lead["email"] from the spread above: a dropped address must not
            # survive into the approval table or the dispatch payload.
            "email": email_block,
            "email_subject": email_subject, "email_body": email_body,
            # meta has 'choice'/'category' — there is no 'source' key, so the old
            # meta.get("source", "general") printed "general" for EVERY lead regardless of
            # what was actually selected, hiding real per-lead personalisation.
            "phone_intl": phone,
            # Which opener the email actually led with, so the render file shows whether a
            # lead got a company-specific line or the generic vertical fallback.
            "opener_source": (site_opener(lead)[1] or "generic"),
            "pain_source": meta.get("category") or meta.get("choice") or "general"}


def write_render_file(rendered: list[dict]) -> None:
    parts = [f"# Outreach render — {datetime.now():%Y-%m-%d %H:%M} (approve in the terminal)\n"]
    for i, r in enumerate(rendered, 1):
        parts.append(f"\n## {i}. {r['company']}  ({r['sector']})")
        parts.append(f"person_id `{r['person_id']}` | phone `{r['phone_intl'] or '-'}` | "
                     f"email `{r['email'] or '-'}` | pain: {r['pain_source']}")
        parts.append(f"\n**WhatsApp** (`{r['wa_template']}`):\n\n```\n{r['wa_preview']}\n```")
        if r["email_body"]:
            parts.append(f"\n**Email** — subject: {r['email_subject']}\n\n```\n{r['email_body']}\n```")
    open(RENDER_FILE, "w", encoding="utf-8").write("\n".join(parts))


def _confirm(prompt: str, on_unanswerable: str) -> bool:
    """Ask a yes/no question that FAILS CLOSED when nobody can answer it.

    Every gate in this script protects an irreversible outward-facing act. A prompt that
    cannot be answered — piped stdin, no TTY, EOF — must therefore mean "no", never "yes".
    """
    if not sys.stdin or not sys.stdin.isatty():
        print(on_unanswerable)
        return False
    try:
        return input(prompt).strip().lower() == "yes"
    except (EOFError, KeyboardInterrupt):
        print(on_unanswerable)
        return False


def review(rendered: list[dict], assume_yes: bool = False) -> list[dict] | None:
    """Compact terminal review. Returns the approved subset, or None if aborted."""
    print(f"\nFull render written to {os.path.basename(RENDER_FILE)} — open it to read every message.")
    print(f"\n{'#':>2} {'vertical':24} {'company':38} {'WA':>2} {'email':28} pain")
    for i, r in enumerate(rendered, 1):
        print(f"{i:>2} {r['sector'][:24]:24} {r['company'][:38]:38} "
              f"{'✓' if r['phone_intl'] else '✗':>2} {(r['email'] or '-')[:28]:28} {r['pain_source']}")
    if assume_yes:
        print(f"\n--yes: approving all {len(rendered)} lead(s) without prompting.")
        return list(rendered)
    # A piped newline READS FINE and used to mean "Enter = ALL", so `printf '\n' | …`
    # silently approved every lead with no human in the loop. Approval of an irreversible
    # send must come from a terminal or from an explicit --yes, never from a pipe.
    if not sys.stdin or not sys.stdin.isatty():
        print("\nstdin is not a terminal — refusing to infer approval. Pass --yes to approve all.")
        return None
    try:
        raw = input("\nApprove: Enter = ALL | numbers to SKIP (e.g. 2,5) | q = abort: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        # Never read an unanswerable prompt as blanket approval of every lead.
        print("\nNo answer possible on this stdin — aborting. Pass --yes to approve all.")
        return None
    if raw in ("q", "quit", "n", "no"):
        return None
    skip = {int(x) for x in re.findall(r"\d+", raw)}
    return [r for i, r in enumerate(rendered, 1) if i not in skip]


def build_send_task(vertical: str, leads: list[dict]) -> str:
    wa_name = leads[0]["wa_template"]
    lead_blocks = []
    for r in leads:
        item = {
            "person_id": r["person_id"], "company": r["company"], "to": r["phone_intl"],
            "wa_template": r["wa_template"], "wa_variables": r["wa_vars"],
        }
        # The email handoff carries VARIABLES, not a rendered body. The body, the operator's
        # signature and the per-vertical PDF all live on the Snov campaign — they cannot be
        # sent from here (Snov has no upload endpoint), so shipping a rendered body would
        # hand over a message that can never be the one actually delivered. What Snov needs
        # is the three custom fields its template renders, and they must match the names
        # snov_push pushes or the recipient is skipped silently.
        if r.get("email"):
            item["email"] = {
                "to": r["email"],
                "subject_line": r.get("subject_line", ""),
                "greeting": lina_compose.greeting(r.get("contact_name") or "",
                                                  short_name(r.get("company") or "")),
                "pain_block": r.get("pain_block", ""),
            }
        lead_blocks.append(item)
    payload = json.dumps(lead_blocks, ensure_ascii=False, indent=1)
    return f"""## EXECUTE SENDS — {vertical} (operator ALREADY approved locally; no gate, no questions)

This is a literal execution checklist. Every decision is already made. Do not rephrase,
re-render, or alter ANY text. Never ask anything: if a step fails, record the exact error
for that lead and continue. End your final output with the marker [DONE] on its own line.

### 1. WhatsApp — for EVERY lead in the JSON below with a non-empty "to"
Use the direct Graph API (the proven primary — Baian's tool 404s on its cached id):
read env NF_BAIAN_WABA_ID + NF_BAIAN_META_TOKEN, discover the phone-number id ONCE via
GET https://graph.facebook.com/v24.0/{{WABA_ID}}/phone_numbers, then for each lead POST
https://graph.facebook.com/v24.0/{{PHONE_NUMBER_ID}}/messages with EXACTLY:
{{"messaging_product":"whatsapp","to":"<to>","type":"template","template":{{"name":"{wa_name}",
"language":{{"code":"ar"}},"components":[{{"type":"body","parameters":[
{{"type":"text","text":"<wa_variables[0]>"}},{{"type":"text","text":"<wa_variables[1]>"}},
{{"type":"text","text":"<wa_variables[2]>"}},{{"type":"text","text":"<wa_variables[3]>"}},
{{"type":"text","text":"<wa_variables[4]>"}}]}}]}}}}
(substitute the five wa_variables strings verbatim, in order).

### 2. Email — ONLY for leads whose JSON block has an "email" object
Enrol the prospect on the vertical's Snov list with its "to" address and these three custom
fields, VERBATIM and under exactly these names: subject_line, greeting, pain_block. Then
start/resume that vertical's campaign. Snov supplies the body, the signature and the PDF —
they live on the campaign, so never compose a body here. Never send with any of the three
fields empty: the campaign skips such a recipient silently. Max 20/day.

### 3. DO NOT touch the CRM. Status updates are handled outside this task.

### 4. REPORT — final output, machine-readable, ONE LINE PER LEAD, exactly this shape:
RESULT | <person_id> | wa=<sent|failed:reason> | email=<sent|failed:reason|none>
Then the totals, then [DONE].

Emit one RESULT line for EVERY lead in the JSON, including failures and skips. Do NOT
summarise them into a table, and do not wrap the lines in bold or code fences. A lead
with no RESULT line is treated as "we cannot tell whether this business was messaged",
which forces a manual reconciliation and risks messaging them a second time.

## LEADS (the complete, final list — nothing else is in scope)
```json
{payload}
```
"""


def apply_crm_updates(report: str, expected_ids: list[str] | None = None) -> tuple[int, int]:
    """Parse RESULT lines and PATCH leadStatus locally. Returns (ok, failed).

    `expected_ids` are the person_ids we submitted for this vertical. Tariq's report is
    free-form prose and DOES sometimes describe the sends in a markdown table while omitting
    the RESULT lines entirely — that happened on the 2026-07-19 Training run: 3 messages went
    out, the regex matched nothing, and the summary read a harmless-looking "0 ok, 0 failed"
    while the CRM still said Not Contacted. Those leads were then one re-run away from being
    messaged twice. Zero parsed results is therefore an ALARM, not a quiet no-op.
    """
    hdr = {"Authorization": f"Bearer {nav_env.env('TWENTY_TOKEN')}",
           "Content-Type": "application/json"}
    ok = fail = 0
    seen: set[str] = set()

    # Two accepted shapes. The RESULT line is what we ASK for, but the runtime is an LLM and
    # the format is a request, not a contract — on 2026-07-19 and again on 2026-07-20 it
    # reported a markdown table instead and 6 confirmed sends went unrecorded. Rather than
    # keep re-asking, read the table too: an unparsed report is indistinguishable from a
    # failed send, and the recovery for that is messaging a real business twice.
    #   RESULT | <uuid> | wa=sent | email=sent
    #   | <uuid> | sent | sent |          <- table row, header/separator rows ignored
    rows = re.findall(
        r"RESULT\s*\|\s*([0-9a-f-]{36})\s*\|\s*wa=(\S+)\s*\|\s*email=(\S+)", report)
    rows += re.findall(
        r"^\s*\|\s*([0-9a-f-]{36})\s*\|\s*([^|\s]+)\s*\|\s*([^|\s]+)\s*\|",
        report, re.M)

    for pid, wa, em in rows:
        if pid in seen:
            continue
        seen.add(pid)
        status = ("Emailed" if em.startswith("sent")
                  else "WhatsApped" if wa.startswith("sent") else None)
        if not status:
            continue
        r = httpx.patch(f"{CRM_BASE}/rest/people/{pid}", headers=hdr,
                        json={"leadStatus": status}, timeout=30)
        ok += r.status_code < 300
        fail += r.status_code >= 300
        print(f"  {'OK ' if r.status_code < 300 else 'ERR'} CRM {pid[:8]} -> {status}")

    missing = [p for p in (expected_ids or []) if p not in seen]
    if missing:
        print("\n  !! CRM STATUS NOT RECORDED for "
              f"{len(missing)} of {len(expected_ids)} lead(s) in this batch.")
        print("     The task report carried no parsable RESULT line for them, so we CANNOT "
              "confirm\n     whether they were messaged. They still read 'Not Contacted' and a "
              "re-run would\n     message them AGAIN. Reconcile before the next send:")
        for p in missing:
            print(f"       PATCH {CRM_BASE}/rest/people/{p}  {{\"leadStatus\": \"...\"}}")
    return ok, fail


def preflight_key_check(force_low_balance: bool = False) -> bool:
    """Fault-1 guard: warn BEFORE submitting send tasks if the cloud's LLM key is near its
    rolling cap or its account is nearly drained (a dead key = silent pending stalls).

    Checks OPENROUTER_API_KEY — the key the CLOUD RUNTIME actually spends when it executes
    these send tasks. It previously checked MY_OPENROUTER_KEY, a personal key the runtime
    never touches; once that key died the guard silently no-op'd through its own except
    branch, leaving the exact failure it exists to prevent completely unguarded.

    THE DECISION IS DELIBERATELY OUTSIDE THE try. It used to sit inside, so a prompt that
    raised — EOF, closed stdin, no TTY — was swallowed by `except Exception` and fell
    through to `return True`: the guard FAILED OPEN and submitted the very sends it had
    just flagged. That happened on 2026-07-19 (153 leads against a $0.91 balance; saved
    only by the provider 402ing). Only the network probe is tolerant now; an unanswerable
    prompt fails CLOSED.
    """
    key = nav_env.env("OPENROUTER_API_KEY")
    if not key:
        print("(!) OPENROUTER_API_KEY not in .env — cannot pre-check the cloud key balance.")
        return True
    try:
        hdr = {"Authorization": f"Bearer {key}"}
        d = httpx.get("https://openrouter.ai/api/v1/auth/key", headers=hdr, timeout=15).json()["data"]
        cr = httpx.get("https://openrouter.ai/api/v1/credits", headers=hdr, timeout=15).json()["data"]
        remaining = d.get("limit_remaining")
        account_left = (cr.get("total_credits") or 0) - (cr.get("total_usage") or 0)
    except Exception as e:
        # Probe failure is not evidence of a bad key — stay permissive here only.
        print(f"(key pre-flight skipped: {e})")
        return True

    print(f"Key pre-flight: window remaining="
          f"{'∞' if remaining is None else f'${remaining:.2f}'} | account left ${account_left:.2f}")
    if not ((remaining is not None and remaining < 0.5) or account_left < 1.0):
        return True

    print("(!) The key is nearly exhausted — cloud tasks will stall SILENTLY in "
          "pending (see POSTMORTEM_2026-07-14 Fault 1). Top up before sending.")
    if force_low_balance:
        print("    --force-low-balance given: submitting anyway.")
        return True
    return _confirm("Submit send tasks anyway? (yes/N) ",
                    "    Refusing to submit on a drained key. Re-run on a terminal, or "
                    "pass --force-low-balance to override deliberately.")


def _fake_leads() -> list[dict]:
    return [
        {"person_id": "00000000-0000-0000-0000-000000000001",
         "company": "شركة الاختبار للمقاولات العامة", "contact_name": "",
         "sector": "Contracting & Facilities", "email": "test@example.com",
         "phone": "112345678", "website": ""},
        {"person_id": "00000000-0000-0000-0000-000000000002",
         "company": "معهد التجربة العالي للتدريب", "contact_name": "",
         "sector": "Training Institutes", "email": "", "phone": "0501234567", "website": ""},
    ]


def resolve_openrouter_key() -> str | None:
    """Pick a WORKING OpenRouter key, and say out loud which one and why.

    There is ONE key now. This used to prefer a personal MY_OPENROUTER_KEY and fall back to
    the shared OPENROUTER_API_KEY, printing a warning about the cloud's rolling daily cap.
    The personal key went dead on 2026-07-21 (401 on every request) and was removed from
    .env on 2026-07-22, so the "preferred" branch could only ever fail and the "fallback"
    was in fact the normal path — the warning fired on every run and meant nothing.

    OPENROUTER_API_KEY is still the shared cloud key with a rolling daily cap (draining it
    is what stalled the pipeline on 2026-07-14), so this is still verified before use and
    still says when it is unusable. It just no longer pretends there is a choice.
    """
    key = nav_env.openrouter_key()
    if key and _key_ok(key):
        print("  pain-classification key: OPENROUTER_API_KEY")
        return key
    if key:
        print("  !! OPENROUTER_API_KEY is INVALID (401) — semantic pain pass DISABLED")
    else:
        print("  !! No OPENROUTER_API_KEY set — semantic pain pass DISABLED")
    print("     (leads fall back to general copy; nothing is fabricated.)")
    return None


def _key_ok(key: str) -> bool:
    try:
        r = httpx.get("https://openrouter.ai/api/v1/key",
                      headers={"Authorization": f"Bearer {key}"}, timeout=20)
        return r.status_code == 200
    except Exception:
        return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verticals", default=",".join(ALL_VERTICALS))
    ap.add_argument("--dry-run", action="store_true", help="render + review, send nothing")
    ap.add_argument("--self-test", action="store_true", help="render fake leads, no CRM/cloud")
    # ON by default (operator decision 2026-07-22). This is what makes {{2}} the lead's OWN
    # coupled pain->solution rather than the vertical's stock paragraph. With it off, every
    # lead in a vertical received the same block — which is both weaker copy and a
    # deliverability signal, and it made the generated composer look like it was working
    # while nothing it produced was ever used.
    ap.add_argument("--llm-pain", action=argparse.BooleanOptionalAction, default=True,
                    help="generate the per-lead pain->solution block and subject "
                         "(OPENROUTER_API_KEY, costs a little). On by default; --no-llm-pain "
                         "falls back to the approved library block.")
    ap.add_argument("--yes", action="store_true",
                    help="approve every rendered lead without prompting (for automation). "
                         "Does NOT override the key-balance guard — that needs "
                         "--force-low-balance, so a drained key still stops an unattended run.")
    ap.add_argument("--email-only", action="store_true",
                    help="send email but NOT WhatsApp. Use when a newly found personal "
                         "email is the only thing that changed: the phone on the record is "
                         "the company switchboard from the Maps listing, not the person's "
                         "mobile, so a WhatsApp would repeat a message that number already "
                         "received — spam to them, and a hit to Meta template quality.")
    ap.add_argument("--email-via", choices=["tariq", "snov"], default="tariq",
                    help="who dispatches the email. 'tariq' (default, unchanged) builds the "
                         "cloud send task. 'snov' instead adds each approved lead to its "
                         "vertical's Snov drip campaign, which is the ONLY path that carries "
                         "the per-vertical PDF attachment and the account signature — both are "
                         "configured once in the Snov dashboard, not per send. Prints the plan "
                         "and stops unless --snov-confirm is also passed.")
    ap.add_argument("--snov-confirm", action="store_true",
                    help="with --email-via snov: actually add the leads. Adding to an ACTIVE "
                         "campaign's list makes Snov SEND to them. Deliberately a separate flag "
                         "from --yes, so approving a render can never also spend a send.")
    ap.add_argument("--enrich", action="store_true",
                    help="run Snov email enrichment for Not Contacted CRM leads. SPENDS "
                         "CREDITS (~1 per lead without an email). Off by default.")
    ap.add_argument("--limit", type=int, default=0,
                    help="cap the batch to the first N leads after all filters (a graduated "
                         "ramp — e.g. a first live batch on a proven template). 0 = no cap.")
    ap.add_argument("--min-employees", type=int, default=0,
                    help="only leads CONFIRMED at this headcount or above, per "
                         "company_size.json (operator rule 2026-07-20: 50+ = high "
                         "priority). Leads whose size was never established are "
                         "EXCLUDED — unknown is not treated as passing.")
    ap.add_argument("--force-low-balance", action="store_true",
                    help="submit send tasks even when the cloud key is nearly exhausted. "
                         "Expect silent pending stalls (POSTMORTEM_2026-07-14 Fault 1).")
    args = ap.parse_args()
    verticals = [v.strip() for v in args.verticals.split(",") if v.strip()]
    bad = [v for v in verticals if v not in ALL_VERTICALS]
    if bad:
        raise SystemExit(f"Unknown vertical(s) {bad}; valid: {ALL_VERTICALS}")
    or_key = resolve_openrouter_key() if args.llm_pain else None

    if args.self_test:
        leads = _fake_leads()
    else:
        print("CRM prep (local, deterministic)…")
        prep.normalize_crm_people()
        # enrich_crm_not_contacted() SPENDS SNOV CREDITS — one domain lookup per Not
        # Contacted lead without an email (29 lookups on 2026-07-20, unannounced, which is
        # how this flag came to exist). Credits are budgeted per-item by the operator, so
        # a render must never quietly consume them: opt in with --enrich.
        if args.enrich:
            prep.enrich_crm_not_contacted()
        else:
            print("  (skipping Snov email enrichment — pass --enrich to spend credits)")
        leads = prep.not_contacted_leads(verticals)
    if not leads:
        print("No Not Contacted leads in those verticals — nothing to do.")
        return

    if args.min_employees:
        # Fail CLOSED: a lead we never sized does not pass the filter. The whole point of
        # the 50+ rule is that it is confirmed per-lead (05 "Sizing a company"), so an
        # unknown must never ride along on the assumption that it might qualify.
        from enrich_company_size import load_cache
        sizes = load_cache()
        before = len(leads)
        leads = [l for l in leads
                 if (sizes.get(l["person_id"], {}).get("employees") or 0) >= args.min_employees]
        print(f"  size filter: {len(leads)}/{before} leads confirmed at "
              f"{args.min_employees}+ employees (unsized leads excluded)")
        if not leads:
            print("No leads meet the size threshold — run scripts/enrich_company_size.py "
                  "(free) then enrich_company_size_snov.py to size more.")
            return

    if args.limit and len(leads) > args.limit:
        print(f"  --limit: capping {len(leads)} lead(s) to the first {args.limit}.")
        leads = leads[:args.limit]

    rendered = [render_lead(l, args.llm_pain, or_key) for l in leads]
    if args.email_only:
        # build_send_task sends WhatsApp to every lead with a non-empty "to", so clearing
        # the number here is what actually suppresses the channel. Leads with no email are
        # dropped rather than silently sent nothing at all.
        without_email = [r["company"] for r in rendered if not r.get("email_body")]
        rendered = [{**r, "phone_intl": ""} for r in rendered if r.get("email_body")]
        print(f"  --email-only: WhatsApp suppressed for {len(rendered)} lead(s)")
        for company in without_email:
            print(f"    skipped (no email, would have had nothing to send): {company[:44]}")
        # Which executive summary each vertical in THIS batch needs. Printed, never sent: the
        # attachment is uploaded once per campaign in the Snov dashboard (no send/attach API
        # exists — see ATTACHMENT above), so the operator needs to know which file to pick.
        verticals = sorted({r.get("sector") or "" for r in rendered} - {""})
        if verticals:
            print("\n  ATTACHMENT per vertical (upload in the Snov campaign, not sent from here):")
            for v in verticals:
                path = attachment_path(v)
                print(f"    {v:26} -> {os.path.basename(path) if path else 'MISSING — check assets/attachments/'}")
    write_render_file(rendered)
    approved = review(rendered, assume_yes=args.yes)
    if approved is None or not approved:
        print("Aborted — nothing sent.")
        return
    if args.self_test or args.dry_run:
        print(f"\n{'SELF-TEST' if args.self_test else 'DRY RUN'} — {len(approved)} approved, "
              f"no tasks created. Render: {RENDER_FILE}")
        return

    # ALTERNATIVE DISPATCH — same approved batch, different carrier. Everything above this line
    # (selection, render, the approval gate) is untouched and shared; only who delivers changes.
    # Snov is the only path that carries the per-vertical PDF and the account signature, because
    # both live on the campaign in Snov's dashboard rather than on the individual message.
    if args.email_via == "snov":
        import snov_push
        # The campaign template renders {{subject_line}}; a prospect without it is SKIPPED
        # by Snov silently (skip_recipients_without_variables_data=true), so it is filled
        # here rather than left to chance. generate_subject falls back to the vertical's
        # approved subject on any failure, so this cannot leave the field empty.
        for r in approved:
            if not r.get("subject_line"):
                vkey = VKEY.get(r.get("sector") or "", "")
                r["subject_line"], _ = lina_compose.generate_subject(
                    vkey, r.get("pains") or None, or_key or "",
                    r.get("pain_summary") or "")
                r["vkey"] = vkey
        failed = snov_push.push(approved, confirm=args.snov_confirm)
        if not args.snov_confirm:
            print("\n(--email-via snov was a DRY RUN. Add --snov-confirm to actually enrol them.)")
        return

    if not preflight_key_check(force_low_balance=args.force_low_balance):
        print("Aborted — nothing sent.")
        return

    cloud = NavaiaForgeClient(api_key=nav_env.env("BUSINESS_NF"), base_url=nav_env.base_url())
    tariq = resolve_agent(cloud, "Tariq")
    by_vertical: dict[str, list[dict]] = {}
    for r in approved:
        by_vertical.setdefault(r["sector"], []).append(r)

    watching = {}
    submitted_ids: dict[str, list[str]] = {}
    for vertical, group in by_vertical.items():
        t = cloud.tasks.create(
            nav_env.CLOUD_WORKFORCE_ID,
            f"SEND (script-approved) Touch-1 — {vertical} ({len(group)} leads)",
            description=build_send_task(vertical, group), agent_id=tariq, priority="high",
            metadata={"kind": "script_authority_send", "vertical": vertical,
                      "leads": len(group)},
        )
        watching[vertical] = t.id
        submitted_ids[vertical] = [r["person_id"] for r in group]
        print(f"✓ {vertical}: send task {t.id} ({len(group)} leads)")

    print("\nWatching sends (Ctrl+C safe — tasks keep running in the cloud)…")
    deadline = time.time() + 1800
    while watching and time.time() < deadline:
        time.sleep(20)
        for vertical, tid in list(watching.items()):
            try:
                t = cloud.tasks.get(tid)
            except Exception as e:
                print(f"  (poll error {vertical}: {e} — retrying)")
                continue
            s = str(t.status).lower()
            if s in ("done", "failed", "cancelled", "waiting_blocked", "waiting_question"):
                print(f"\n===== {vertical}: {s.upper()} =====")
                report = t.result or ""
                print(report[:2500])
                if s == "done":
                    ok, fail = apply_crm_updates(report, submitted_ids.get(vertical))
                    print(f"CRM updates: {ok} ok, {fail} failed")
                del watching[vertical]
    if watching:
        print(f"\nStill running after 30 min: {watching} — rerun later or check the dashboard.")


if __name__ == "__main__":
    main()

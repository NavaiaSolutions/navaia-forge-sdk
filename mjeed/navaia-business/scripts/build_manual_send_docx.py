#!/usr/bin/env python3
"""Build the manual-send DOCX: every outreach template plus the exact send settings.

Purpose: let the operator send by hand (phone, Zoho web, WhatsApp Business app) and have
the message land looking and reading EXACTLY like the automated pipeline's send.

Sources of truth, read at build time so the doc cannot drift:
  - workforce/04_outreach_templates.md  : the verbatim copy (email touches, WA bodies)
  - scripts/outreach.py                 : CAL, SIG, VKEY, TRIGGER, EMAIL_PAIN + the HTML
                                          wrapper the pipeline puts around every email body

Output: NAVAIA_Manual_Send_Playbook.docx at repo root.
"""
from __future__ import annotations

import ast
import os
import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt, RGBColor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_MD = os.path.join(ROOT, "workforce", "04_outreach_templates.md")
OUTREACH_PY = os.path.join(ROOT, "scripts", "outreach.py")
OUT = os.path.join(ROOT, "NAVAIA_Manual_Send_Playbook.docx")

# The pipeline's email body styling (scripts/outreach.py, render_lead). Kept as one dict so
# the doc states the real numbers rather than a prose approximation of them.
EMAIL_STYLE = {
    "font": "Arial",
    "size_pt": 11,
    "line_spacing": 1.6,
    "direction": "RTL (right-to-left), right-aligned",
    "color": "default black — the pipeline sets no colour, so the mail client default wins",
}

ACCENT = RGBColor(0x1F, 0x4E, 0x79)
MUTED = RGBColor(0x60, 0x60, 0x60)


# ---------------------------------------------------------------- source extraction

def outreach_constants() -> dict:
    """Pull module-level literals out of outreach.py without importing it.

    outreach.py imports navaia_forge and the CRM client at module scope; parsing the AST
    keeps this generator runnable on any machine with no backend credentials.
    """
    tree = ast.parse(open(OUTREACH_PY, encoding="utf-8").read())
    wanted = {"CAL", "SIG", "VKEY", "TRIGGER", "EMAIL_PAIN", "CRM_BASE"}
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name) and t.id in wanted:
                out[t.id] = ast.literal_eval(node.value)
    missing = wanted - out.keys()
    if missing:
        raise SystemExit(f"outreach.py no longer defines: {sorted(missing)}")
    return out


def parse_templates_md() -> tuple[dict, dict]:
    """Split the templates markdown into per-vertical email touches and WA bodies.

    Returns (verticals, whatsapp) where
      verticals[title] = {"pain": str, "lexicon": str, "touches": [(label, subject, body)]}
      whatsapp[label]  = {"name": str, "body": str}
    """
    text = open(TEMPLATES_MD, encoding="utf-8").read()
    verticals: dict[str, dict] = {}
    whatsapp: dict[str, dict] = {}

    # Vertical sections: "## Vertical N (Tier X) : <arabic> (<english>) : REFERENCE"
    for m in re.finditer(r"^## (Vertical \d.*)$", text, re.M):
        title = m.group(1).strip()
        start = m.end()
        nxt = re.search(r"^## ", text[start:], re.M)
        section = text[start:start + nxt.start()] if nxt else text[start:]

        pain = ""
        pm = re.search(r"^Pain \(per the vertical one-pager\):(.+?)(?=\n\*\*Field|\n### )",
                       section, re.S | re.M)
        if pm:
            # The one-pager text is bolded in markdown; the docx has no use for the markers.
            pain = re.sub(r"\*\*(.+?)\*\*", r"\1", " ".join(pm.group(1).split()))
        lex = ""
        lm = re.search(r"^\*\*Field lexicon:\*\*(.+)$", section, re.M)
        if lm:
            lex = lm.group(1).strip()

        touches = []
        for tm in re.finditer(r"^### (Touch \d[^\n]*)\n(.*?)(?=^### |\Z)", section, re.S | re.M):
            label, chunk = tm.group(1).strip(), tm.group(2)
            sm = re.search(r"\*\*الموضوع:\*\*\s*(.+)", chunk)
            subject, alt = "", ""
            if sm:
                raw = sm.group(1).strip()
                subject = re.split(r"\s*\*\(alt", raw)[0].strip().strip("`* ")
                am = re.search(r"\*\(alt:\s*`([^`]+)`\)\*", raw)
                if am:
                    alt = am.group(1)
                chunk = chunk[sm.end():]
            body = chunk.strip().strip("-").strip()
            touches.append({"label": label, "subject": subject, "alt": alt, "body": body})

        verticals[title] = {"pain": pain, "lexicon": lex, "touches": touches}

    # WhatsApp sections: "### WhatsApp Touch 1 : <label> (`name`, APPROVED…)" + fenced body
    for m in re.finditer(
            r"^### WhatsApp Touch 1 : ([^(\n]+)\(`([^`]+)`[^\n]*\n(.*?)```\n(.*?)```",
            text, re.S | re.M):
        label, name, _pre, body = m.groups()
        whatsapp[label.strip()] = {"name": name.strip(), "body": body.strip()}

    if not verticals or not whatsapp:
        raise SystemExit("Could not parse 04_outreach_templates.md — its headings changed.")
    return verticals, whatsapp


# ---------------------------------------------------------------- docx helpers

def _rtl(par, run=None):
    """Mark a paragraph (and run) right-to-left the way Word expects.

    python-docx has no RTL API; Word needs w:bidi on the paragraph and w:rtl on each run,
    or Arabic punctuation lands on the wrong side of the line.
    """
    pPr = par._p.get_or_add_pPr()
    bidi = OxmlElement("w:bidi")
    pPr.append(bidi)
    par.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    if run is not None:
        rPr = run._element.get_or_add_rPr()
        rtl = OxmlElement("w:rtl")
        rPr.append(rtl)
        # Arabic is rendered with the "complex script" font slot, not the latin one.
        rFonts = rPr.find(qn("w:rFonts"))
        if rFonts is None:
            rFonts = OxmlElement("w:rFonts")
            rPr.append(rFonts)
        rFonts.set(qn("w:cs"), EMAIL_STYLE["font"])
        szCs = OxmlElement("w:szCs")
        szCs.set(qn("w:val"), str(EMAIL_STYLE["size_pt"] * 2))  # half-points
        rPr.append(szCs)


def arabic_block(doc, text: str):
    """Render copy exactly as the pipeline renders it: Arial 11pt, 1.6 line, RTL, right."""
    for line in text.split("\n"):
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = EMAIL_STYLE["line_spacing"]
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(line)
        r.font.name = EMAIL_STYLE["font"]
        r.font.size = Pt(EMAIL_STYLE["size_pt"])
        _rtl(p, r)
    return p


def note(doc, text: str, italic=True):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(text)
    r.italic = italic
    r.font.size = Pt(9)
    r.font.color.rgb = MUTED
    return p


def kv_table(doc, rows: list[tuple[str, str]]):
    t = doc.add_table(rows=0, cols=2)
    t.style = "Light Grid Accent 1"
    for k, v in rows:
        cells = t.add_row().cells
        cells[0].text = k
        cells[1].text = v
        for par in cells[0].paragraphs:
            for run in par.runs:
                run.bold = True
                run.font.size = Pt(9)
        for par in cells[1].paragraphs:
            for run in par.runs:
                run.font.size = Pt(9)
    doc.add_paragraph()
    return t


def heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = ACCENT
    return h


# ---------------------------------------------------------------- document

def build():
    C = outreach_constants()
    verticals, whatsapp = parse_templates_md()

    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)

    doc.add_heading("NAVAIA — Manual Send Playbook", 0)
    note(doc, "Every outreach template plus the exact settings the automated pipeline uses. "
              "Send by hand from these pages and the message arrives identical to an "
              "automated send.", italic=False)
    note(doc, "Generated from workforce/04_outreach_templates.md and scripts/outreach.py. "
              "Regenerate with: python scripts/build_manual_send_docx.py")

    # ---- 1. Email settings
    heading(doc, "1. Email — send settings", 1)
    kv_table(doc, [
        ("Mailbox / from", "ops@navaia.sa (Zoho), the same mailbox Snov.io sends through"),
        ("Format", "HTML (not plain text)"),
        ("Direction", EMAIL_STYLE["direction"]),
        ("Font", f'{EMAIL_STYLE["font"]}, {EMAIL_STYLE["size_pt"]}pt'),
        ("Line spacing", str(EMAIL_STYLE["line_spacing"])),
        ("Colour", EMAIL_STYLE["color"]),
        ("Signature", "DO NOT type one. The Zoho/Snov account signature is appended "
                      "server-side; a typed signature double-stamps."),
        ("Subject", "use the short subject as given (≤3 words, <30 chars so it survives the "
                    "mobile cutoff). A per-lead alt is offered where listed."),
        ("Cadence", "Touch 1 day 0, Touch 2 day +3, Touch 3 day +7. Max 5 touches ever."),
        ("Send window", "Sunday–Thursday, roughly 10:00–12:00 AST. Never Friday or Saturday."),
        ("Daily volume", "max 20 emails per day"),
        ("Booking link", C["CAL"]),
        ("Sender name", C["SIG"]),
    ])

    heading(doc, "The exact HTML wrapper", 2)
    note(doc, "The pipeline wraps every email body in this one div. If you paste into a "
              "client that lets you edit HTML, use it verbatim; if you can only type, set "
              "the font, size, line spacing and right-to-left direction to match.")
    code = doc.add_paragraph()
    r = code.add_run(
        f'<div dir="rtl" style="text-align: right; direction: rtl; '
        f'font-family: {EMAIL_STYLE["font"]}, sans-serif; '
        f'font-size: {EMAIL_STYLE["size_pt"]}pt; '
        f'line-height: {EMAIL_STYLE["line_spacing"]};">…body, newlines as &lt;br&gt;…</div>')
    r.font.name = "Consolas"
    r.font.size = Pt(8.5)

    # ---- 2. Token fills
    heading(doc, "2. What to type into each token", 1)
    note(doc, "The templates carry {tokens}. These are what the pipeline substitutes — "
              "fill them the same way by hand.")
    kv_table(doc, [
        ("{honorific+name}", "الأستاذ <contact name> when you have a name; otherwise "
                             "القائمون على <short business name> الكرام"),
        ("{اسم الشركة} / {اسم العيادة} / {اسم المعهد}", "the business name, per vertical"),
        ("{inbound_context}", "always empty — leave it out entirely"),
        ("{trigger_line}", "a fact the company publishes about its own scale, phrased as "
                           "the opener — coverage, branches, projects, clients or years in "
                           "business. Only if their site actually states it. Otherwise the "
                           "generic per-vertical line listed below."),
        ("{lina_pain}", "the lead's specific pain as a noun phrase; when you have nothing "
                        "lead-specific, use the per-vertical default listed below"),
    ])
    note(doc, "Rule that overrides convenience: never say or imply you read their reviews. "
              "State the pain as a known, fixable pain in their line of work.")

    heading(doc, "Per-vertical fallback fills", 2)
    note(doc, "Use these when the company's site states nothing concrete. Never invent a "
              "number to fill the opener — the generic line is the correct answer when "
              "there is no fact.")
    rows = []
    for v, line in C["TRIGGER"].items():
        rows.append((f"{v} — {{trigger_line}}", line))
        rows.append((f"{v} — {{lina_pain}}", C["EMAIL_PAIN"].get(v, "")))
    kv_table(doc, rows)

    active = set(C["VKEY"].keys())
    note(doc, "Active verticals right now: " + "، ".join(sorted(active)) +
              ". Private Clinics and Finance & Debt Collection are retired in the pipeline — "
              "their copy is kept below for reference only.")

    # ---- 3. Email templates
    heading(doc, "3. Email templates", 1)
    for title, data in verticals.items():
        heading(doc, title, 2)
        if data["pain"]:
            note(doc, "Pain: " + data["pain"])
        if data["lexicon"]:
            note(doc, "Field lexicon: " + data["lexicon"])
        for t in data["touches"]:
            heading(doc, t["label"], 3)
            if t["subject"]:
                p = doc.add_paragraph()
                p.add_run("Subject: ").bold = True
                sr = p.add_run(t["subject"])
                sr.font.name = EMAIL_STYLE["font"]
                _rtl(p, sr)
                if t["alt"]:
                    note(doc, "alt subject: " + t["alt"])
            arabic_block(doc, t["body"])
            doc.add_paragraph()

    # ---- 4. WhatsApp
    doc.add_page_break()
    heading(doc, "4. WhatsApp — send settings", 1)
    kv_table(doc, [
        ("Channel", "WhatsApp Business API (Meta), template message, language ar"),
        ("When", "first contact only. Touch 2 and 3 go as free text inside the 24h window "
                 "after they reply."),
        ("Phone format", "international, no +: drop a leading 0 and prefix 966 "
                         "(0501234567 → 966501234567, 112350077 → 966112350077)"),
        ("Landlines", "920 and 011 numbers do run WhatsApp Business — do not filter to "
                      "mobile-only"),
        ("Formatting", "none. WhatsApp renders the approved body as-is; no font, size or "
                       "colour is settable."),
        ("Body", "must match the Meta-approved body verbatim — Meta can alter a body during "
                 "approval, so send only what is printed here."),
    ])
    heading(doc, "Variable map (same for every template)", 2)
    kv_table(doc, [
        ("{{1}}", "honorific + name (as in the email token above)"),
        ("{{2}}", "the coupled pain → solution block. Must name the automation "
                  "(…تتولّى) and must not cite reviews."),
        ("{{3}}", "business name"),
        ("{{4}}", C["CAL"]),
        ("{{5}}", C["SIG"]),
    ])

    heading(doc, "5. WhatsApp templates (approved, verbatim)", 1)
    for label, wa in whatsapp.items():
        heading(doc, f'{label.strip()} — {wa["name"]}', 2)
        arabic_block(doc, wa["body"])
        doc.add_paragraph()

    # ---- 6. Replies
    heading(doc, "6. On a positive reply", 1)
    note(doc, "Check cal.com first — they may have booked from the link. Reply within "
              "minutes, not hours.")
    doc.add_paragraph().add_run("A) Replied, no booking yet:").bold = True
    arabic_block(doc, "يسعدني ذلك. تفضّلوا باختيار الوقت الأنسب لكم هنا: "
                      f"{C['CAL']} أو أرسلوا لي وقتاً مناسباً على واتساب لأتّصل بكم.")
    doc.add_paragraph()
    doc.add_paragraph().add_run("B) Already booked via the link:").bold = True
    arabic_block(doc, "شكراً لكم، وصلني حجزكم وسأتّصل بكم في الموعد الذي اخترتموه. "
                      "وإن رغبتم في تقديمه أو تأجيله فأنا رهن إشارتكم.")

    heading(doc, "Ramadan variant (all verticals)", 2)
    note(doc, "Add under the greeting: رمضان مبارك، أعاده الله عليكم بالخير. Soften the CTA "
              "verb, keep the closing question, drop urgency. Send early morning or "
              "post-iftar; avoid mid-afternoon.")

    doc.save(OUT)
    print(f"wrote {OUT}")
    print(f"  {len(verticals)} verticals, "
          f"{sum(len(v['touches']) for v in verticals.values())} email touches, "
          f"{len(whatsapp)} WhatsApp templates")


if __name__ == "__main__":
    build()

#!/usr/bin/env python3
"""Watch ops@navaia.sa for replies to outreach and push them to Telegram.

The gap this closes: nothing monitors the inbox. Outreach goes out, and a prospect who
answers sits unread until someone happens to look. Our own pitch to these leads is that
every minute of delay cools a warm lead — this is that hole in our own pipeline.

WHY IMAP AND NOT SNOV'S REPLY TRACKING
Snov exposes GET /v2/campaigns/{id}/replies, but on 2026-07-20 it reported zero replies
across all 62 campaigns ever sent — because Snov detects replies by reading the connected
mailbox, and IMAP is disabled on the Zoho account. Reading IMAP directly is both the fix
and the better sensor: it sees every reply, including ones Snov would misclassify, and it
does not depend on campaign state. Enabling IMAP also repairs Snov's own tracking.

PREREQUISITE (one-time, Zoho admin console):
    Mail Settings -> IMAP Access -> Enable, for ops@navaia.sa
    If the account has 2FA, generate an app-specific password and put THAT in ZOHO_PASS.
Until then this script exits with instructions rather than a stack trace.

What it does NOT do: reply to anyone. It surfaces the message and the lead's context so a
human answers. Auto-replying to a cold prospect on our behalf is not a decision a poller
should make.

Usage:
    python scripts/watch_replies.py                # one pass
    python scripts/watch_replies.py --loop 300     # poll every 5 minutes
    python scripts/watch_replies.py --dry-run      # print, don't send to Telegram
    python scripts/watch_replies.py --since-days 7 # widen the first look-back
"""
from __future__ import annotations

import argparse
import email
import email.utils
import imaplib
import io
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from email.header import decode_header, make_header

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import httpx

import nav_env
import pipeline_prep as prep

STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "replies_seen.json")
IMAP_HOST = "imap.zoho.com"

# Machine mail that is not a human answering us. Matching on the ADDRESS, not the subject,
# because Arabic out-of-office subjects vary too much to enumerate.
_MACHINE_SENDER = re.compile(
    r"(mailer-daemon|postmaster|no-?reply|noreply|do-?not-?reply|bounce|notifications?@)", re.I)
# Auto-submitted per RFC 3834 — the reliable signal for vacation/OOO autoresponders.
_AUTO_HEADERS = ("auto-submitted", "x-autoreply", "x-autorespond", "x-auto-response-suppress")


def _decode(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw)))
    except Exception:
        return raw


def _body_text(msg: email.message.Message) -> str:
    """Best-effort plain text of a message, HTML stripped if that is all there is."""
    parts = []
    if msg.is_multipart():
        for p in msg.walk():
            if p.get_content_type() == "text/plain" and "attachment" not in str(p.get("Content-Disposition") or ""):
                try:
                    parts.append(p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", "replace"))
                except Exception:
                    continue
    if not parts:
        try:
            raw = msg.get_payload(decode=True) or b""
            text = raw.decode(msg.get_content_charset() or "utf-8", "replace")
            parts.append(re.sub(r"<[^>]+>", " ", text) if "<" in text else text)
        except Exception:
            pass
    text = "\n".join(parts)
    # Trim the quoted thread — we want THEIR words, not our own message echoed back.
    text = re.split(r"\n\s*(?:On .+ wrote:|-----Original Message-----|من:|في .+ كتب)", text)[0]
    return " ".join(text.split())[:900]


def preflight() -> imaplib.IMAP4_SSL | None:
    """Connect, or explain exactly what to switch on. Never raises."""
    user, pw = nav_env.env("ZOHO_MAIL"), nav_env.env("ZOHO_PASS")
    if not user or not pw:
        print("ZOHO_MAIL / ZOHO_PASS missing from .env — cannot read the mailbox.")
        return None
    try:
        m = imaplib.IMAP4_SSL(IMAP_HOST, 993, timeout=20)
        m.login(user, pw)
        return m
    except imaplib.IMAP4.error as e:
        detail = str(e)
        print(f"IMAP login failed for {user}: {detail[:160]}")
        if "yet to enable IMAP" in detail or "not enabled" in detail.lower():
            print("\n  FIX (one-time, ~2 minutes):")
            print("    Zoho Mail admin console -> Mail Settings -> IMAP Access -> Enable")
            print(f"    for {user}. If the account uses 2FA, generate an app-specific")
            print("    password and put that in ZOHO_PASS (not the login password).")
            print("\n  This also repairs Snov's own reply tracking, which has recorded")
            print("  zero replies across every campaign because it cannot read the inbox.")
        elif "AUTHENTICATIONFAILED" in detail:
            print("\n  Credentials rejected. If 2FA is on, ZOHO_PASS must be an")
            print("  APP-SPECIFIC password, not the account password.")
        return None
    except Exception as e:
        print(f"Could not reach {IMAP_HOST}: {type(e).__name__}: {str(e)[:120]}")
        return None


def load_state() -> dict:
    try:
        with io.open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"seen": []}


def save_state(state: dict) -> None:
    state["seen"] = state["seen"][-2000:]  # bounded; message-ids are never reused
    tmp = STATE + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


# Consumer mail hosts. Some leads' CRM address is a free mailbox (a real one in our data is
# on hotmail.com), and such a lead must NEVER put "hotmail.com" into the domain index —
# every reply from any Hotmail user on earth would then be attributed to that one company.
# Domain matching is only meaningful for a domain the business actually owns.
# Deliberately no real address here: this file is mirrored into a PUBLIC repo, and a
# customer's mailbox in a code comment is personal data under PDPL.
_FREE_MAIL = {
    "gmail.com", "hotmail.com", "outlook.com", "outlook.sa", "live.com", "yahoo.com",
    "icloud.com", "me.com", "aol.com", "protonmail.com", "proton.me", "yandex.com",
    "msn.com", "googlemail.com", "hotmail.co.uk", "yahoo.co.uk",
}


def contacted_leads() -> dict:
    """email address -> lead, and domain -> lead, for everyone we actually messaged.

    Matching on domain as well as address matters: the reply often comes from a person
    (ahmed@company.sa) when we wrote to info@company.sa. Exact-address matching always
    wins; the domain index is the fallback and excludes consumer mail hosts.
    """
    by_addr, by_domain = {}, {}
    for p in prep._crm_people():
        if p.get("leadStatus") in ("Not Contacted", None):
            continue
        addr = ((p.get("emails") or {}).get("primaryEmail") or "").lower()
        lead = {
            "person_id": p["id"],
            "company": (p.get("company") or {}).get("name") or "",
            "sector": p.get("sector") or "",
            "status": p.get("leadStatus") or "",
            "email": addr,
        }
        if addr:
            by_addr[addr] = lead
            domain = addr.split("@")[-1]
            if domain not in _FREE_MAIL:
                by_domain.setdefault(domain, lead)
    return {"addr": by_addr, "domain": by_domain}


def telegram(text: str, dry_run: bool = False) -> bool:
    token, chat = nav_env.env("TELEGRAM_BOT_TOKEN"), nav_env.env("TELEGRAM_CHAT_ID")
    if dry_run or not token or not chat:
        print("\n--- TELEGRAM (not sent) ---\n" + text + "\n---")
        return False
    r = httpx.post(f"https://api.telegram.org/bot{token}/sendMessage",
                   json={"chat_id": chat, "text": text, "parse_mode": "HTML",
                         "disable_web_page_preview": True}, timeout=30)
    if r.status_code >= 300:
        print(f"  telegram failed {r.status_code}: {r.text[:150]}")
    return r.status_code < 300


def scan(m: imaplib.IMAP4_SSL, leads: dict, state: dict, since_days: int,
         dry_run: bool, set_status: bool) -> int:
    m.select("INBOX")
    since = (datetime.now() - timedelta(days=since_days)).strftime("%d-%b-%Y")
    typ, data = m.search(None, f'(SINCE "{since}")')
    ids = data[0].split() if data and data[0] else []
    print(f"  {len(ids)} message(s) since {since}")

    hits = 0
    for num in ids:
        typ, raw = m.fetch(num, "(RFC822)")
        if not raw or not raw[0]:
            continue
        msg = email.message_from_bytes(raw[0][1])
        mid = msg.get("Message-ID") or f"{num!r}"
        if mid in state["seen"]:
            continue

        from_addr = (email.utils.parseaddr(msg.get("From") or "")[1] or "").lower()
        state["seen"].append(mid)

        if _MACHINE_SENDER.search(from_addr) or any(msg.get(h) for h in _AUTO_HEADERS):
            continue  # bounce or vacation autoresponder, not a person

        lead = leads["addr"].get(from_addr) or leads["domain"].get(from_addr.split("@")[-1])
        if not lead:
            continue  # not one of our outreach leads

        subject = _decode(msg.get("Subject"))
        when = _decode(msg.get("Date"))
        body = _body_text(msg)
        hits += 1

        text = (f"📬 <b>REPLY from {lead['company'] or from_addr}</b>\n"
                f"<b>Sector:</b> {lead['sector']}  |  <b>We sent:</b> {lead['status']}\n"
                f"<b>From:</b> {from_addr}\n<b>When:</b> {when}\n"
                f"<b>Subject:</b> {subject}\n\n{body}\n\n"
                f"CRM: https://crm.navaia.sa/object/person/{lead['person_id']}")
        telegram(text, dry_run)
        print(f"  REPLY  {lead['company'][:38]:38} <- {from_addr}")

        # CRM status is best-effort. The 'Replied' option could not be verified (the
        # metadata API returns 403), so a rejected PATCH must not lose the alert we
        # already delivered — the Telegram push is the load-bearing output here.
        if set_status and not dry_run:
            ok = prep._patch_person(lead["person_id"], {"leadStatus": "Replied"})
            print(f"         CRM -> Replied: {'ok' if ok else 'REJECTED (check the enum)'}")

    save_state(state)
    return hits


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, default=0, help="poll every N seconds")
    ap.add_argument("--since-days", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true", help="print instead of sending")
    ap.add_argument("--set-status", action="store_true",
                    help="also set CRM leadStatus=Replied (enum unverified; best-effort)")
    args = ap.parse_args()

    while True:
        m = preflight()
        if not m:
            raise SystemExit(1)
        try:
            leads = contacted_leads()
            print(f"watching {len(leads['addr'])} contacted lead(s)…")
            n = scan(m, leads, load_state(), args.since_days, args.dry_run, args.set_status)
            print(f"  {n} new repl{'y' if n == 1 else 'ies'}")
        finally:
            try:
                m.logout()
            except Exception:
                pass
        if not args.loop:
            return
        time.sleep(args.loop)


if __name__ == "__main__":
    main()

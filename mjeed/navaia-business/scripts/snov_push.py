#!/usr/bin/env python3
"""Push approved leads into a per-vertical Snov drip campaign.

WHY THIS EXISTS (probed live 2026-07-21, not taken from a doc):
Snov has no ad-hoc send endpoint — `/v1/send-email` and `/v1/campaigns/send` both 404 — and
`POST /v2/campaigns` returns 403, so a campaign cannot be CREATED from here. But
`POST /v1/add-prospect-to-list` returns 200 with the current key. That split is the whole
design:

  - ONCE per vertical, in the Snov DASHBOARD: create the drip campaign, attach that vertical's
    executive-summary PDF (see outreach.ATTACHMENT), set the Zoho mailbox as sender, configure
    the signature and the 0/+3/+7 sequence. This is the only place a file can be attached.
  - EVERY batch, from here: add each approved lead to that campaign's list. Snov then sends it
    with the attachment, the signature and the sequencing already configured.

So the PDF is attached once per vertical, never per send.

This is an ALTERNATIVE dispatch for the email channel, not a replacement for anything. The
existing Tariq/cloud path is unchanged and remains the default.

SPENDING: adding a prospect to a list that belongs to an ACTIVE campaign causes Snov to send to
that person. This script therefore prints the plan and STOPS unless `--yes` is passed, per the
standing rule that a script never spends on its own initiative.

Usage:
    python scripts/snov_push.py --campaigns              # list campaigns + list_ids, to map them
    python scripts/snov_push.py --show-map               # what vertical -> list_id is configured
    python scripts/snov_push.py --push leads.json        # dry run: print exactly what would happen
    python scripts/snov_push.py --push leads.json --yes  # actually add them (Snov will send)
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import httpx

import lina_compose
import nav_env

API = "https://api.snov.io"

# vertical -> Snov list_id. Kept in a file rather than in code because the ids only exist once
# the operator has built the campaigns in the dashboard, and they differ per account. An env
# override wins, so a container can be pointed at different campaigns without editing anything.
MAP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "snov_lists.json")

ENV_KEY = {
    "Real Estate": "NAVAIA_SNOV_LIST_REALESTATE",
    "Contracting & Facilities": "NAVAIA_SNOV_LIST_CONTRACTING",
    "Training Institutes": "NAVAIA_SNOV_LIST_TRAINING",
}


def token() -> str:
    cid, csec = nav_env.env("SNOV_USER_ID"), nav_env.env("SNOV_USER_SECRET")
    if not cid or not csec:
        raise SystemExit("SNOV_USER_ID / SNOV_USER_SECRET missing — cannot authenticate.")
    r = httpx.post(f"{API}/v1/oauth/access_token", timeout=30, data={
        "grant_type": "client_credentials", "client_id": cid, "client_secret": csec})
    r.raise_for_status()
    return r.json()["access_token"]


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def campaigns(tok: str) -> list[dict]:
    r = httpx.get(f"{API}/v2/campaigns", headers=_h(tok), timeout=30)
    r.raise_for_status()
    return r.json().get("data", [])


def load_map() -> dict:
    """vertical -> list_id, from the env first, then the mapping file."""
    out: dict[str, int] = {}
    try:
        with io.open(MAP_FILE, encoding="utf-8") as f:
            raw = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        raw = {}
    for k, v in (raw.items() if isinstance(raw, dict) else []):
        # Per-KEY conversion. Wrapping the whole loop in one try meant the "_readme" string
        # raised ValueError on int() and discarded every real mapping with it — a configured
        # vertical then read as unmapped and its leads were silently skipped.
        if k.startswith("_") or not v:
            continue
        try:
            out[k] = int(v)
        except (TypeError, ValueError):
            continue
    for vertical, key in ENV_KEY.items():
        val = nav_env.env(key, "")
        if val:
            try:
                out[vertical] = int(val)
            except ValueError:
                continue
    return out


# The Snov custom field that carries the per-lead Arabic written HERE. The campaign template
# references it as {{pain_block}}; Snov supplies the PDF, the signature and the sender, and the
# repo supplies the copy. That split exists because Snov's API has NO file-upload endpoint, so
# an attachment can only ever live on a dashboard campaign — while copy generated per lead can
# only ever come from here.
#
# The name must match a field DEFINED in Snov first. An undefined name is rejected with
# 422 "Custom fields [x] not found" (probed 2026-07-21), which is a loud, safe failure.
PAIN_FIELD = nav_env.env("NAVAIA_SNOV_PAIN_FIELD", "pain_block") or "pain_block"

# The finished greeting. Snov templates have no conditionals, so the person-vs-company
# choice and the gendered honorific are decided HERE, where the lead data is, and shipped as
# one string. greeting() never returns empty, which matters: these campaigns set
# skip_recipients_without_variables_data=true, so an empty variable drops the recipient
# silently instead of mailing them.
GREET_FIELD = nav_env.env("NAVAIA_SNOV_GREET_FIELD", "greeting") or "greeting"

# The per-lead subject. Varying it also helps deliverability: an identical subject across a
# whole batch is itself a spam signal. Falls back to the vertical's APPROVED subject, so a
# generation failure costs nothing and can never leave this empty.
SUBJ_FIELD = nav_env.env("NAVAIA_SNOV_SUBJECT_FIELD", "subject_line") or "subject_line"


def add_prospect(tok: str, list_id: int, lead: dict) -> tuple[bool, str]:
    """Add one lead to a Snov list. Returns (ok, detail). Never raises on a bad row."""
    email = (lead.get("email") or "").strip()
    if not email:
        return False, "no email"

    # REFUSE a lead with no copy. The template renders {{pain_block}} unconditionally, so an
    # empty value does not fail — it sends a message with a hole in it, under the operator's
    # name, and nothing downstream would report that as an error.
    block = (lead.get("pain_block") or lead.get("block") or "").strip()
    if not block:
        return False, f"no {PAIN_FIELD} — refusing to send a message with a gap in it"

    # Never empty: an empty subject variable would make Snov skip the recipient silently,
    # and a subjectless mail is a spam signal anyway.
    subject = (lead.get("subject_line") or "").strip() or lina_compose.SUBJECT_FALLBACK.get(
        (lead.get("vkey") or "").strip().lower(), "")
    if not subject:
        return False, f"no {SUBJ_FIELD} and no approved fallback for this vertical"

    # updateContact=1 is REQUIRED, not an optimisation. Without it Snov returns
    # success=true / added=false / updated=false for an address it already knows and
    # silently keeps the OLD field values — so a re-pushed lead would send with the previous
    # lead's copy, or with an empty {{pain_block}} rendering a hole in the message. Probed
    # live 2026-07-21: the same call flips to added=true/updated=true with this flag set.
    payload = {"listId": list_id, "email": email, "updateContact": 1,
               f"customFields[{PAIN_FIELD}]": block,
               f"customFields[{GREET_FIELD}]": lina_compose.greeting(
                   lead.get("contact_name") or "", lead.get("company") or ""),
               f"customFields[{SUBJ_FIELD}]": subject}

    name = (lead.get("contact_name") or "").strip()
    if name:
        # Send the split parts too. Snov's {{first_name}} does NOT derive from fullName, so a
        # template greeting rendered empty while fullName looked correctly populated.
        payload["fullName"] = name
        parts = name.split()
        payload["firstName"] = parts[0]
        if len(parts) > 1:
            payload["lastName"] = " ".join(parts[1:])
    company = (lead.get("company") or "").strip()
    if company:
        payload["companyName"] = company
    try:
        r = httpx.post(f"{API}/v1/add-prospect-to-list", headers=_h(tok), data=payload, timeout=30)
    except Exception as e:                       # one bad row must not sink the batch
        return False, f"error {str(e)[:60]}"
    if r.status_code != 200:
        return False, f"http {r.status_code} {r.text[:80]}"
    body = r.json()
    if not body.get("success"):
        return False, str(body)[:80]
    # added/updated are Snov's own dedup signal — a lead already in the list is NOT an error,
    # but it must be reported, because it means Snov will not re-enrol them.
    state = "added" if body.get("added") else ("updated" if body.get("updated") else "already present")
    return True, state


def push(leads: list[dict], confirm: bool) -> int:
    """Add each lead to its vertical's list. Prints the plan; sends only when confirm is True."""
    mapping = load_map()
    if not mapping:
        raise SystemExit(
            "No vertical -> list_id mapping configured.\n"
            "Build one campaign per vertical in the Snov dashboard (attach that vertical's PDF),\n"
            "then run --campaigns to read the list_ids and write them into snov_lists.json.")

    by_vertical: dict[str, list[dict]] = {}
    unmapped: dict[str, int] = {}
    for lead in leads:
        v = lead.get("sector") or ""
        if v in mapping:
            by_vertical.setdefault(v, []).append(lead)
        else:
            unmapped[v] = unmapped.get(v, 0) + 1

    print(f"{len(leads)} lead(s) in the batch\n")
    for v, rows in sorted(by_vertical.items()):
        withm = sum(1 for r in rows if (r.get("email") or "").strip())
        print(f"  {v:26} list {mapping[v]}  {len(rows)} lead(s), {withm} with an email")
    for v, n in sorted(unmapped.items()):
        print(f"  {v or '(no sector)':26} NOT MAPPED — {n} lead(s) would be SKIPPED")

    if not confirm:
        print("\nDRY RUN — nothing added, nothing sent. Re-run with --yes to add them.")
        print("Adding to an ACTIVE campaign's list makes Snov SEND to these people.")
        return 0

    tok = token()
    ok = fail = 0
    for v, rows in sorted(by_vertical.items()):
        print(f"\n{v} -> list {mapping[v]}")
        for lead in rows:
            good, detail = add_prospect(tok, mapping[v], lead)
            ok, fail = ok + int(good), fail + int(not good)
            print(f"  {'OK  ' if good else 'FAIL'} {(lead.get('company') or '')[:38]:38} {detail}")
    print(f"\n{ok} added/updated, {fail} failed, {sum(unmapped.values())} skipped (unmapped vertical)")
    return fail


def set_map(pairs: list[str]) -> None:
    """Write vertical -> list_id into MAP_FILE, resolving each from a CAMPAIGN id.

    Takes the campaign id rather than the list_id on purpose: the campaign is what the operator
    actually sees and names in the dashboard, while list_id is an internal number that is easy to
    transcribe from the wrong row — and a wrong row here enrols real leads into the wrong
    sequence, which cannot be undone once Snov sends.
    """
    tok = token()
    by_id = {str(c["id"]): c for c in campaigns(tok)}
    try:
        with io.open(MAP_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"expected VERTICAL=CAMPAIGN_ID, got: {pair}")
        vertical, cid = (p.strip() for p in pair.split("=", 1))
        if vertical not in ENV_KEY:
            raise SystemExit(f"unknown vertical {vertical!r}. One of: {', '.join(ENV_KEY)}")
        c = by_id.get(cid)
        if not c:
            raise SystemExit(f"no campaign with id {cid} on this account (run --campaigns)")
        data[vertical] = c["list_id"]
        print(f"  {vertical:26} -> list {c['list_id']}   [{c['status']}] {c['campaign']}")

    with io.open(MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nwritten to {os.path.basename(MAP_FILE)}")
    print("CHECK THE CAMPAIGN NAMES ABOVE match the vertical each is mapped to before pushing.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaigns", action="store_true", help="list campaigns and their list_ids")
    ap.add_argument("--map", nargs="+", metavar="VERTICAL=CAMPAIGN_ID",
                    help='map verticals to campaigns, e.g. --map "Real Estate=3083558"')
    ap.add_argument("--show-map", action="store_true", help="show the configured vertical -> list_id")
    ap.add_argument("--push", metavar="LEADS_JSON", help="a JSON array of rendered leads")
    ap.add_argument("--yes", action="store_true", help="actually add them (Snov will send)")
    args = ap.parse_args()

    if args.campaigns:
        for c in campaigns(token()):
            print(f"  id={c['id']:<9} list_id={c['list_id']:<10} {c['status']:<10} {c['campaign']}")
        return
    if args.map:
        set_map(args.map)
        return
    if args.show_map:
        mapping = load_map()
        if not mapping:
            print("nothing configured — see snov_lists.json / NAVAIA_SNOV_LIST_* env vars")
        for v, lid in mapping.items():
            print(f"  {v:26} -> {lid}")
        return
    if args.push:
        with io.open(args.push, encoding="utf-8") as f:
            leads = json.load(f)
        sys.exit(1 if push(leads, args.yes) else 0)
    ap.print_help()


if __name__ == "__main__":
    main()

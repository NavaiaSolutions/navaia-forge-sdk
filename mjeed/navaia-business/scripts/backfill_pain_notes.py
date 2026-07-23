#!/usr/bin/env python3
"""Carry each lead's review-derived pain into the CRM as a Note — so the local pool can go.

    python scripts/backfill_pain_notes.py --dry-run     # show every note it would write
    python scripts/backfill_pain_notes.py               # write them

## Why a Note, and why this unblocks deleting the pool file

`pain_hints` is the composer's grounding for 136 leads, and Twenty has NO field to hold it:
the metadata API answers 403 for this key, so `place_id`, `rating` and `pain_hints` cannot
become real columns (audited 2026-07-22). Until now those five facts were rescued only into
`discovery_state.json`, a LOCAL file — which meant the pain lived nowhere the shared CRM
could see and nothing but this laptop could read. A Note is the one place Twenty will hold
free text keyed to a company, so that is where it goes. Once it is here, the pool file's
unique contribution is in the production CRM, not a local rescue file, and the file is
genuinely redundant rather than merely copied.

## What it is, and the rule it must not break

The hints are RAW customer-review snippets — internal sales intelligence, never outreach
copy. `workforce/04_outreach_templates.md` forbids citing a customer's reviews back to them,
and that rule is about what we SEND. Storing the raw signal in an internal CRM note is the
opposite: it is the grounding the composer abstracts AWAY from. The note says so on its face,
so no one later pastes a snippet into a message.

## Boundaries

* Company-level: pain is about the business, so the note targets the COMPANY record.
* Only leads already IN the CRM (a `company_id` in `discovery_state.json`) get a note — a
  portal or a qualify-dropped lead has no record to attach to, and inventing one is exactly
  the fabrication the rules forbid.
* Idempotent: a company that already carries this note is skipped, so a re-run never stacks
  duplicates. Safe to run repeatedly, and safe to run after the enrichment loop.
* Fail-closed: a note whose id cannot be read back is reported as ORPHANED, never counted as
  written. Nothing here spends credits or sends anything.
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

import nav_env
import crm_write
import polite_fetch
import discover

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
POOL = nav_env.env("NAVAIA_LEADS_FILE") or os.path.join(ROOT, "leads_enriched_people.json")
CRM = crm_write.CRM
NOTE_TITLE = "Review-derived pain signals (internal)"


def _note_id(payload: dict) -> str | None:
    """Id out of a /rest/notes response — createNote, NOT crm_write._extract_id (which knows
    only create/updatePerson|Company and would silently return None for a note)."""
    data = payload.get("data") or {}
    for key in ("createNote", "updateNote"):
        if key in data:
            return (data[key] or {}).get("id")
    return data.get("id")


def note_body(hints: list[str]) -> str:
    lines = "\n".join(f"- {h}" for h in hints if str(h).strip())
    return (
        "INTERNAL sales intelligence — NOT outreach copy. These are raw customer-review "
        "signals used to decide which pain the message leads with. Per the copy rules they "
        "must never be quoted back to the customer; the composer abstracts away from them.\n\n"
        f"{lines}"
    )


def company_has_note(company_id: str) -> bool:
    """True if this company already carries the pain note — the idempotency check."""
    try:
        r = httpx.get(f"{CRM}/rest/noteTargets", headers=crm_write.headers(),
                      params={"filter": f"targetCompanyId[eq]:{company_id}", "limit": 60},
                      timeout=30)
        r.raise_for_status()
        targets = r.json().get("data", {}).get("noteTargets", [])
    except httpx.HTTPError:
        return False
    for t in targets:
        nid = t.get("noteId")
        if not nid:
            continue
        try:
            n = httpx.get(f"{CRM}/rest/notes/{nid}", headers=crm_write.headers(),
                          timeout=30).json().get("data", {}).get("note", {})
        except httpx.HTTPError:
            continue
        if (n.get("title") or "") == NOTE_TITLE:
            return True
    return False


def write_note(company_id: str, hints: list[str]) -> bool:
    body = {"title": NOTE_TITLE, "bodyV2": {"markdown": note_body(hints)},
            "createdBy": crm_write.CREATED_BY}
    try:
        r = httpx.post(f"{CRM}/rest/notes", headers=crm_write.headers(), json=body, timeout=30)
        r.raise_for_status()
        nid = _note_id(r.json())
        if not nid:
            print(f"    WARN note created but id unreadable — ORPHANED: {r.text[:100]}")
            return False
        t = httpx.post(f"{CRM}/rest/noteTargets", headers=crm_write.headers(),
                       json={"noteId": nid, "targetCompanyId": company_id}, timeout=30)
        t.raise_for_status()
        return True
    except (httpx.HTTPError, ValueError) as e:
        print(f"    WARN note not written: {str(e)[:100]}")
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pool", default=os.path.abspath(POOL))
    args = ap.parse_args()

    pool = [l for l in json.load(io.open(args.pool, encoding="utf-8")) if isinstance(l, dict)]
    done = polite_fetch.load_store(discover.STATE_PATH).get("done", {})

    # Pain source is the pool; if a lead somehow lacks it there, fall back to the rescue
    # facts in discovery_state — the two should agree, but the checkpoint is the backup that
    # exists precisely so nothing is lost.
    def hints_for(lead) -> list[str]:
        h = lead.get("pain_hints")
        if h:
            return [x for x in h if str(x).strip()]
        facts = (done.get(discover.lead_key(lead)) or {}).get("facts") or {}
        return [x for x in (facts.get("pain_hints") or []) if str(x).strip()]

    todo, no_id, no_pain = [], 0, 0
    for lead in pool:
        hints = hints_for(lead)
        if not hints:
            no_pain += 1
            continue
        cid = (done.get(discover.lead_key(lead)) or {}).get("company_id")
        if not cid:
            no_id += 1                 # portal / qualify-dropped — no record to attach to
            continue
        todo.append((cid, lead.get("name", "?"), hints))

    print(f"pool={len(pool)}  with-pain={len(todo)+no_id}  attachable={len(todo)}  "
          f"(skipped: {no_id} no CRM record, {no_pain} no pain)\n")

    written = skipped = failed = 0
    for cid, name, hints in todo:
        if not args.dry_run and company_has_note(cid):
            skipped += 1
            print(f"  SKIP (already noted)  {name[:34]}")
            continue
        if args.dry_run:
            print(f"  [dry-run] NOTE -> {name[:34]:34} ({len(hints)} hint(s)) company {cid[:8]}")
            written += 1
            continue
        if write_note(cid, hints):
            written += 1
            print(f"  OK  {name[:34]:34} {len(hints)} hint(s)")
        else:
            failed += 1

    print(f"\n{'DRY RUN — ' if args.dry_run else ''}"
          f"notes {'planned' if args.dry_run else 'written'}={written}  "
          f"skipped={skipped}  failed={failed}")
    if not args.dry_run:
        print("Pain now lives in the CRM. discovery_state.json still holds the backup; the "
              "POOL file's unique data is no longer only local.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

"""Publish the outreach template library into a workforce knowledge base.

Splits workforce/04_outreach_templates.md into per-section text docs (doctrine,
one per vertical, reply-handling, Ramadan, WhatsApp) and pushes each into a KB
named "NAVAIA Outreach Templates" so agents can search the exact template + the
verbatim Meta-approved WhatsApp bodies instead of reciting from memory.

Idempotent: creates the KB once (reuses if present) and only adds text docs
whose title isn't already there — safe to re-run, never duplicates.

    python scripts/build_templates_kb.py            # publish/refresh
    python scripts/build_templates_kb.py --reset     # delete all texts first, then republish
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import httpx
from navaia_forge import NavaiaForgeClient

import nav_env

KB_NAME = "NAVAIA Outreach Templates"
WF = nav_env.CLOUD_WORKFORCE_ID
BASE = nav_env.base_url().rstrip("/")
KEY = nav_env.env("BUSINESS_NF")
SRC = os.path.join(os.path.dirname(__file__), "..", "workforce", "04_outreach_templates.md")
H = {"X-API-Key": KEY, "Content-Type": "application/json", "Accept": "application/json"}


def sections() -> list[tuple[str, str]]:
    """Split the templates md into (title, content) chunks on top-level ## headings."""
    text = open(SRC, encoding="utf-8").read()
    parts = re.split(r"(?m)^(##\s+.*)$", text)
    out: list[tuple[str, str]] = []
    intro = parts[0].strip()
    if intro:
        out.append(("Outreach — overview & update notes", intro))
    for i in range(1, len(parts), 2):
        heading = parts[i].lstrip("# ").strip()
        body = (parts[i] + parts[i + 1]).strip() if i + 1 < len(parts) else parts[i].strip()
        # Compact the title (drop the "(Tier X) :" noise) but keep it recognisable.
        title = re.sub(r"\s+", " ", heading)[:120]
        out.append((title, body))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="Delete existing texts before publishing.")
    args = ap.parse_args()

    cloud = NavaiaForgeClient(api_key=KEY, base_url=BASE)

    kb = next((k for k in cloud.knowledge.list(workforce_id=WF) if k.name == KB_NAME), None)
    if kb is None:
        kb = cloud.knowledge.create(
            KB_NAME, workforce_id=WF, source_type="blank",
            description="Outreach template library: per-vertical email touches, the 5 Meta-approved "
                        "WhatsApp bodies, doctrine, reply-handling and Ramadan variant. Search by vertical/channel.",
        )
        print(f"created KB {kb.id}")
    else:
        print(f"reusing KB {kb.id}")

    with httpx.Client(timeout=40) as c:
        existing = c.get(f"{BASE}/api/v1/knowledge-bases/{kb.id}/texts", headers=H)
        rows = existing.json() if existing.status_code < 300 else []
        if isinstance(rows, dict):
            rows = rows.get("items") or rows.get("texts") or []
        have = {r.get("title") for r in rows}
        if args.reset:
            for r in rows:
                c.delete(f"{BASE}/api/v1/knowledge-bases/{kb.id}/texts/{r.get('id')}", headers=H)
            print(f"reset: deleted {len(rows)} existing texts")
            have = set()

        added = skipped = 0
        for title, content in sections():
            if title in have:
                skipped += 1
                continue
            r = c.post(f"{BASE}/api/v1/knowledge-bases/{kb.id}/texts", headers=H,
                       json={"title": title, "content": content})
            if r.status_code < 300:
                added += 1
                print(f"  + {title}")
            else:
                print(f"  ! {title}: HTTP {r.status_code} {r.text[:120]}")
        print(f"\ndone: added {added}, skipped {skipped} (already present)")
        print(f"KB id: {kb.id}  name: {KB_NAME!r}")


if __name__ == "__main__":
    main()

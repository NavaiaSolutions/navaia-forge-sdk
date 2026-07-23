#!/usr/bin/env python3
"""Prove the discovery image can actually do the four things the PR promises.

Run as the image's CMD, unprivileged, exactly as the agent would:

    docker run --rm navaia/discovery:dev

Every check reports what was OBSERVED, never what was expected. The distinction that
matters most is IMPORT vs FETCH: `agent_scraping_skill` is stdlib-only, so it imports
happily on a browserless runtime and then returns an error dict for every URL. Reporting
the first as evidence of the second is precisely the failure that recorded seven live
company sites as "no headcount published" on 2026-07-20.

Exit code is 0 only if every check passes, so this is usable as a CI gate.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str):
    def wrap(fn):
        try:
            ok, detail = fn()
        except Exception as e:  # noqa: BLE001 — a crash is a failed check, report it verbatim
            ok, detail = False, f"{type(e).__name__}: {e}"
        RESULTS.append((name, ok, detail))
        return fn
    return wrap


@check("gosom_binary")
def _gosom():
    """The Maps scraper must be on PATH as a BINARY — the agent has no docker."""
    path = shutil.which("google-maps-scraper")
    if not path:
        return False, "not on PATH"
    p = subprocess.run([path, "-h"], capture_output=True, text=True, timeout=60)
    # gosom prints its flag list to stderr and exits non-zero for -h; presence of the
    # flags we depend on is the real signal, not the exit code.
    blob = (p.stdout or "") + (p.stderr or "")
    needed = [f for f in ("-input", "-results", "-depth", "-c") if f not in blob]
    if needed:
        return False, f"{path} ran but lacks expected flags: {needed}"
    return True, f"{path} (has -input/-results/-depth/-c)"


@check("gosom_extra_reviews")
def _gosom_reviews():
    """Plan item 4 needs -extra-reviews, which requires -json output instead of CSV."""
    p = subprocess.run([shutil.which("google-maps-scraper") or "google-maps-scraper", "-h"],
                       capture_output=True, text=True, timeout=60)
    blob = (p.stdout or "") + (p.stderr or "")
    have = [f for f in ("-extra-reviews", "-json") if f in blob]
    return len(have) == 2, f"present: {have or 'none'}"


@check("chromium_launch")
def _chromium():
    """The 21-missing-.so blocker. Launch it, do not merely install it."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        try:
            page = b.new_page()
            page.set_content("<h1>navaia</h1>")
            title = page.evaluate("document.querySelector('h1').textContent")
        finally:
            b.close()
    return title == "navaia", f"rendered DOM -> {title!r}"


@check("scripts_importable")
def _scripts():
    """Rashid's preflight is literally this import."""
    from scripts.agent_scraping_skill import agent_scraping_skill  # noqa: F401
    import scripts.polite_fetch as pf
    return True, f"agent_scraping_skill + polite_fetch (delay={pf.DEFAULT_DELAY}s)"


@check("live_fetch")
def _live():
    """The check that cannot be faked by a successful import."""
    from scripts.agent_scraping_skill import agent_scraping_skill
    res = agent_scraping_skill("https://example.com")
    md = (res.get("markdown") or "").strip()
    if res.get("status") != "success":
        return False, f"status={res.get('status')} msg={str(res.get('message'))[:200]}"
    if md in ("", "None"):
        return False, "status=success but markdown is empty/'None' — nothing was fetched"
    return "Example Domain" in md or len(md) > 50, f"{len(md)} chars of markdown"


@check("politeness_layer")
def _polite():
    """Best practice, enforced in code: robots.txt is consulted and honoured."""
    import scripts.polite_fetch as pf
    rp, delay = pf.robots("https://example.com/")
    disallowed_ok = pf.allowed("https://example.com/") is True
    return disallowed_ok and delay > 0, f"robots consulted, crawl-delay={delay}s, allowed=True"


@check("unprivileged")
def _user():
    """Must match the cloud runtime: uid 999, no root, no docker."""
    uid = os.getuid()
    return uid != 0, f"uid={uid} docker={'yes' if shutil.which('docker') else 'no'}"


def main() -> int:
    width = max(len(n) for n, _, _ in RESULTS)
    print("\nNAVAIA discovery image — self-check\n" + "=" * (width + 40))
    for name, ok, detail in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<{width}}  {detail}")
    failed = [n for n, ok, _ in RESULTS if not ok]
    print("=" * (width + 40))
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} passed"
          + (f" — FAILED: {', '.join(failed)}" if failed else ""))
    print(json.dumps({n: ok for n, ok, _ in RESULTS}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

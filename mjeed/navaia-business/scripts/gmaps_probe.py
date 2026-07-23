#!/usr/bin/env python3
"""Does Google serve Maps to THIS IP? One tiny burst, logged — run it spaced over days.

    python scripts/gmaps_probe.py                       # one probe burst, appends to log
    python scripts/gmaps_probe.py --query "شركة مقاولات الرياض" --depth 1
    python scripts/gmaps_probe.py --show                # print the log, run nothing

## The question it answers, and why one run cannot

Baking the gosom binary into the cloud image (`deploy/discovery/Dockerfile` does this) makes
the binary PRESENT. It does not prove Google will SERVE a datacenter IP — Google blocks
cloud ASNs far more readily than residential ones, sometimes on the very first query. gosom
hides that failure: a blocked request comes back as ZERO rows, not an error, so a single run
that returns nothing is ambiguous — blocked, or a query that genuinely matched nothing?

The instrument is therefore the LOG OVER TIME, not any one run. An IP can also *warm into* a
block: burst 1 succeeds, burst 3 starts returning nothing. Only a spaced sequence reveals
that. So this script does exactly ONE small burst per invocation and appends the result to a
log; the CADENCE is external — schedule it (cron, or the `schedule` skill) every 8-12h for a
few days and read the trend.

## Footprint and safety

Deliberately minimal: ONE query, depth 1, so a probe is the smallest possible Google
footprint — the opposite of the 24/7 crawl that earns a block. It writes NOTHING to the CRM,
enriches nothing, spends no credits, and never touches the pool. It records the egress IP
(best effort) so the log shows which IP each result came from — the cloud runtime and a
laptop can then be compared directly.

Read `--source gmaps` in discover.py for the real scrape; this shares its invocation shape
so a probe result is representative of what a real burst would get.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import time
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import nav_env
import polite_fetch
import discover
import distill_scraped_leads as distill

LOG_PATH = os.path.join(polite_fetch.state_dir(), "gmaps_probe_log.json")

# Strings Google's block/consent surfaces leave in gosom's stderr. gosom-rod usually just
# yields zero rows, but when it does log something, these disambiguate "blocked" from
# "genuinely empty". Not exhaustive — the row count across the log is the primary signal.
BLOCK_MARKERS = ("consent.google", "captcha", "recaptcha", "unusual traffic",
                 "/sorry/", "are you a robot", "automated queries")


def egress_ip() -> dict:
    """Best-effort {ip, org}. A probe that cannot look up its own IP still runs — the log
    just records 'unknown', never a fabricated address."""
    try:
        import httpx
        r = httpx.get("https://ipinfo.io/json", timeout=10)
        if r.status_code < 300:
            d = r.json()
            return {"ip": d.get("ip", "unknown"), "org": d.get("org", "")}
    except Exception:  # noqa: BLE001 — the probe's job is gosom, not IP lookup
        pass
    return {"ip": "unknown", "org": ""}


def one_burst(query: str, depth: str, binary: str) -> dict:
    """Run a single tiny gosom query. Return a log record — never raises for a block."""
    out_dir = polite_fetch.state_dir()
    qpath = os.path.join(out_dir, "probe_query.txt")
    rpath = os.path.join(out_dir, "probe_result.json")
    with io.open(qpath, "w", encoding="utf-8") as f:
        f.write(query + "\n")
    for stale in (rpath,):
        try:
            os.remove(stale)
        except OSError:
            pass

    if not (os.path.exists(binary) or _which(binary)):
        return {"verdict": "no-binary",
                "note": f"{binary!r} not on PATH — this runtime has no scraper"}

    cmd = [binary, "-input", qpath, "-results", rpath, "-json",
           "-depth", depth, "-c", "1", "-geo", discover.GMAPS_GEO, "-lang", "ar",
           "-zoom", discover.GMAPS_ZOOM, "-exit-on-inactivity", "90s"]
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    elapsed = round(time.time() - t0, 1)

    rows = 0
    if os.path.exists(rpath):
        try:
            rows = len(distill.read_records(rpath))
        except Exception:  # noqa: BLE001
            rows = 0

    stderr = (proc.stderr or "")[-600:]
    blocked = any(m in stderr.lower() for m in BLOCK_MARKERS)

    if rows > 0:
        verdict = "served"          # unambiguous: Google answered this IP
    elif blocked:
        verdict = "blocked"         # a consent/CAPTCHA marker showed up
    else:
        verdict = "empty"           # zero rows, no marker — suspicious but not proof
    return {"verdict": verdict, "rows": rows, "seconds": elapsed,
            "exit": proc.returncode, "stderr_tail": stderr.strip()[-300:]}


def _which(binary: str) -> str | None:
    import shutil
    return shutil.which(binary)


def load_log() -> list[dict]:
    try:
        with io.open(LOG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def append_log(record: dict) -> None:
    log = load_log()
    log.append(record)
    tmp = LOG_PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=1)
    os.replace(tmp, LOG_PATH)


def print_log(log: list[dict]) -> None:
    if not log:
        print("No probe runs logged yet.")
        return
    print(f"\n{'when':20} {'ip':16} {'verdict':9} {'rows':>4}  org")
    print("-" * 78)
    for r in log:
        print(f"{r.get('at','')[:19]:20} {str(r.get('ip','?'))[:16]:16} "
              f"{r.get('verdict','?'):9} {str(r.get('rows','-')):>4}  {str(r.get('org',''))[:24]}")
    served = sum(r.get("verdict") == "served" for r in log)
    empty = sum(r.get("verdict") == "empty" for r in log)
    blocked = sum(r.get("verdict") == "blocked" for r in log)
    nobin = sum(r.get("verdict") == "no-binary" for r in log)
    print(f"\n{len(log)} run(s): {served} served, {empty} empty, {blocked} blocked"
          + (f", {nobin} no-binary" if nobin else "") + ".")
    if nobin and not (served or empty or blocked):
        print("Only no-binary runs — this host has no scraper, so the probe cannot judge "
              "the IP. Run it where the gosom binary is on PATH (the deployed cloud image).")
        return
    if served and (empty or blocked):
        print("MIXED — the IP is served SOMETIMES. That is the warm-into-block pattern: a "
              "cloud IP is not reliably usable. Keep gosom on a residential runner.")
    elif served and not (empty or blocked):
        print("Consistently SERVED. If every run is from the cloud IP, cloud-side scraping "
              "is viable — proceed, but keep probing, Google can change its mind.")
    elif not served:
        print("NEVER served. Either the query is wrong, or this IP is blocked. Compare a "
              "run from a laptop: if the laptop gets rows and this IP does not, it is the IP.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--query", default="شركة مقاولات الرياض",
                    help="one Maps query — keep it a real, populous one so 'empty' means blocked")
    ap.add_argument("--depth", default="1", help="scroll depth; 1 = smallest footprint")
    ap.add_argument("--gmaps-binary",
                    default=nav_env.env("NAVAIA_GMAPS_BINARY") or "google-maps-scraper")
    ap.add_argument("--show", action="store_true", help="print the log and exit")
    args = ap.parse_args()

    if args.show:
        print_log(load_log())
        return 0

    ip = egress_ip()
    print(f"probe from ip={ip['ip']} ({ip['org'] or 'org unknown'})  query={args.query!r}")
    result = one_burst(args.query, args.depth, args.gmaps_binary)
    record = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "query": args.query,
              "depth": args.depth, **ip, **result}
    append_log(record)

    print(f"  verdict={record['verdict']}  rows={record.get('rows','-')}  "
          f"exit={record.get('exit','-')}  {record.get('seconds','-')}s")
    if record["verdict"] == "empty":
        print("  zero rows, no block marker — INCONCLUSIVE on its own. The log across "
              "several spaced runs is what settles it.")
    if record.get("stderr_tail"):
        print(f"  stderr: {record['stderr_tail'][:160]}")
    print_log(load_log())
    return 0


if __name__ == "__main__":
    sys.exit(main())

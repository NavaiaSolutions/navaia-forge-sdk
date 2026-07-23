#!/usr/bin/env python3
"""Shared crawling layer: robots.txt, rate limiting, a page cache, and atomic state.

Every scraper in this repo should fetch through here. Three reasons it exists:

1. COMPLIANCE. The obligations that carry real legal weight when crawling are honouring
   robots.txt and rate limiting — a crawler that respects Crawl-delay and backs off has not
   been found liable under CFAA "damage" or trespass-to-chattels. This logic lived inside
   enrich_company_size.py, so enrich_emails_crawl4ai.py (which called the scraper directly)
   had NO robots check and NO delay and crawled at full speed. Found 2026-07-20.

2. ONE FETCH, MANY EXTRACTORS. Headcount, site facts, emails and people all live in the same
   HTML, but each extractor used to crawl the site again — at 12s per host that is ~96s of
   sleeping per lead to read the same pages twice. PageCache fetches a URL once per lead and
   every extractor reads from it.

3. NOT LOSING WORK. A crawl is slow and a partially-finished run must keep what it earned.
   The disk cache survives a kill, and save_store() re-reads before writing so two concurrent
   runs cannot erase each other — a plain dump destroyed real results twice on 2026-07-20.

Nothing here is local-only: paths come from NAVAIA_STATE_DIR so the same code runs in a cloud
runtime unchanged.
"""
from __future__ import annotations

import hashlib
import io
import ipaddress
import json
import os
import socket
import sys
import time
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nav_env
from agent_scraping_skill import agent_scraping_skill
from micro_scraper import USER_AGENT

# One request per 10-15s is the documented norm for small sites; a site's own stated
# Crawl-delay always wins over this default.
DEFAULT_DELAY = 12.0
PAGE_TTL_DAYS = float(nav_env.env("DISCOVER_PAGE_TTL_DAYS", "14") or 14)

_robots_cache: dict[str, tuple[object, float]] = {}
_last_hit: dict[str, float] = {}

# Arabic-Indic digits -> ASCII once, at fetch time, so every downstream regex can assume
# ASCII numerals without repeating the translation.
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def state_dir() -> str:
    """Where run state and cached pages live. Overridable for containers."""
    default = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    return nav_env.env("NAVAIA_STATE_DIR", default) or default


def norm(text: str) -> str:
    return (text or "").translate(_AR_DIGITS)


# ── robots + rate limiting ────────────────────────────────────────────────────────

def robots(base: str) -> tuple[object, float]:
    """(parser, crawl_delay) for a host. A missing or broken robots.txt means 'allowed'."""
    host = urlparse(base).netloc
    if host in _robots_cache:
        return _robots_cache[host]
    rp = RobotFileParser()
    rp.set_url(urljoin(base, "/robots.txt"))
    delay = DEFAULT_DELAY
    try:
        rp.read()
        stated = rp.crawl_delay(USER_AGENT) or rp.crawl_delay("*")
        if stated:
            delay = max(float(stated), 1.0)  # obey the site's own number
    except Exception:
        rp = None  # unreachable robots.txt is not a prohibition
    _robots_cache[host] = (rp, delay)
    return rp, delay


def allowed(url: str) -> bool:
    rp, _ = robots(url)
    if rp is None:
        return True
    try:
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        return True


def throttle(url: str) -> None:
    """Sleep so we never hit the same host faster than its crawl delay."""
    host = urlparse(url).netloc
    _, delay = robots(url)
    elapsed = time.time() - _last_hit.get(host, 0.0)
    if elapsed < delay:
        time.sleep(delay - elapsed)
    _last_hit[host] = time.time()


def is_public_url(url: str) -> bool:
    """True only for an http(s) URL that resolves to a PUBLIC address.

    Every URL reaching fetch() comes from a scraped `website` field — data written by
    strangers on a Google Maps listing, not by us. Without this check that value chooses
    what the crawler connects to, which is a server-side request forgery: in the cloud
    runtime `http://169.254.169.254/` is the instance metadata service, and its response
    would be stored in the page cache and then fed to the model as if it were a company's
    About page. `file://` would do the same for local files.

    So: http(s) only, and every resolved address must be global. Resolution happens here
    rather than trusting the hostname, because a name under someone else's control can
    simply point at a private address. This is not airtight against a DNS rebind between
    this check and the request — closing that needs pinning at the socket layer — but it
    stops the whole class of attack that a scraped field actually enables.
    """
    try:
        parts = urlparse(url)
    except ValueError:
        return False
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return False
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or
                                   (443 if parts.scheme == "https" else 80),
                                   proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, ValueError):
        return False            # unresolvable is a miss, exactly like an unreachable site
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        # is_global excludes loopback, link-local (metadata), private, reserved and
        # multicast in one predicate — safer than enumerating ranges by hand.
        if not ip.is_global:
            return False
    return bool(infos)


def fetch(url: str) -> str:
    """Markdown for one URL, or '' on any failure. Never raises — a dead site is a miss.

    Returns '' for a robots-disallowed path too: a page we are not permitted to read is
    recorded as unknown, exactly like an unreachable one. We do not fetch it anyway.
    """
    # Before robots, before throttling: a non-public target is not a site we are choosing
    # to be polite to, it is a request we must not make at all.
    if not is_public_url(url):
        return ""
    if not allowed(url):
        return ""
    throttle(url)
    try:
        res = agent_scraping_skill(url)
    except Exception:
        return ""
    if res.get("status") != "success":
        return ""
    md = res.get("markdown") or ""
    # A failed crawl used to arrive here as the 4-character string "None" — truthy, and
    # therefore counted as a page that simply had nothing on it. Never let a non-page
    # masquerade as a silent one.
    if md.strip() in ("", "None"):
        return ""
    return norm(md)


# ── page cache ───────────────────────────────────────────────────────────────────

class PageCache:
    """Fetch each URL at most once, memoised in memory and on disk.

    Disk backing is what makes an interrupted crawl cheap to resume: the 12-second delay
    per page is the expensive part, not the parsing, so a re-run should never re-pay it for
    a page it already has. A URL that returned nothing is remembered as a miss and not
    retried within the same run.
    """

    def __init__(self, ttl_days: float = PAGE_TTL_DAYS):
        self.ttl = ttl_days * 86400
        self.pages: dict[str, str] = {}
        self.misses: set[str] = set()
        self.root = os.path.join(state_dir(), "pagecache")

    def _path(self, url: str) -> str:
        host = urlparse(url).netloc or "nohost"
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
        return os.path.join(self.root, host, digest + ".md")

    def get(self, url: str) -> str:
        if url in self.pages:
            return self.pages[url]
        if url in self.misses:
            return ""
        path = self._path(url)
        try:
            if time.time() - os.path.getmtime(path) < self.ttl:
                with io.open(path, encoding="utf-8") as f:
                    md = f.read()
                self.pages[url] = md
                return md
        except (OSError, ValueError):
            pass

        md = fetch(url)
        if not md:
            self.misses.add(url)
            return ""
        self.pages[url] = md
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".tmp"
            with io.open(tmp, "w", encoding="utf-8") as f:
                f.write(md)
            os.replace(tmp, path)
        except OSError:
            pass  # a cache we cannot persist is still a cache we can use this run
        return md

    def get_many(self, base: str, paths: list[str], budget: int) -> dict[str, str]:
        """Fetch up to `budget` paths under `base`, skipping ones already known missing."""
        out: dict[str, str] = {}
        for path in paths:
            if len(out) >= budget:
                break
            url = urljoin(base, path) if path else base
            md = self.get(url)
            if md:
                out[url] = md
        return out

    @property
    def fetched_count(self) -> int:
        return len(self.pages)


# ── atomic, merge-on-write JSON state ────────────────────────────────────────────

def load_store(path: str) -> dict:
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_store(path: str, data: dict) -> None:
    """Merge into whatever is on disk, then write atomically.

    A plain dump of an in-memory dict is a lost-update bug when two runs overlap: on
    2026-07-20 a long crawl holding a stale snapshot erased a completed enrichment pass,
    one save at a time. Re-reading before every write means a concurrent writer's entries
    survive, and os.replace means a kill mid-write cannot truncate the file.
    """
    merged = load_store(path)
    merged.update(data)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    data.update(merged)  # keep the caller's view consistent with disk


def merge_keep_known(prior: dict, fresh: dict) -> dict:
    """Field-level merge where a pass that found NOTHING never erases a known value.

    Absence of evidence in this run is not evidence of absence. A re-crawl for one purpose
    (say, people) must not wipe a headcount another source already established — that
    happened on 2026-07-20 and silently dropped leads out of the qualified set.
    """
    out = dict(prior)
    for key, value in fresh.items():
        if value in (None, "", [], {}):
            continue
        out[key] = value
    return out


if __name__ == "__main__":
    if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if len(sys.argv) < 2:
        raise SystemExit("usage: polite_fetch.py <url>  — fetch one page politely")
    url = sys.argv[1]
    print(f"allowed={allowed(url)}  delay={robots(url)[1]}s  state_dir={state_dir()}")
    cache = PageCache()
    md = cache.get(url)
    print(f"{len(md)} chars")
    print(md[:600])

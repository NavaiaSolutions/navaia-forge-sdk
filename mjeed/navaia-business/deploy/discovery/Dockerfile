# NAVAIA discovery runtime — every scraping technique in ONE image.
#
# This is not a sidecar. It is the layer the AGENT RUNTIME image must contain, because
# the agent cannot reach any capability that is not already in its own container:
#
#   * `tools` on an agent is a fixed integration registry (crm/snov/baian/zoho). There is
#     no way to register a custom scrape() function, so capability cannot arrive that way.
#   * runtime_mode is `navaia_code`, so the agent's real tool surface is the SHELL. Probed
#     live 2026-07-21: it ran ls, ldd, pip and `playwright install` and returned real output.
#   * The agent has NO docker, NO root, NO sudo, and apt-get is permission-denied
#     (uid 999). So `docker run gosom/...` — what the laptop playbook does today — can
#     never work from inside the agent. gosom has to be a plain binary on PATH.
#
# Everything below is therefore a BUILD-TIME root operation. None of it can be bootstrapped
# at runtime, which is why it has to ride in the PR rather than be installed later.
#
# Base is pinned to Debian 13 (trixie) + Python 3.12 to match the measured cloud runtime
# (`3.12.13`, trixie, uid 999) — so what verifies here is what runs there.

# ── Stage 1: the Google Maps scraper binary ────────────────────────────────────────────
# `latest-rod` is the verified-working tag. The plain `latest`/v1.16.x tags are broken
# upstream (Playwright driver bug, issue #302) — see deploy/gmaps-scraper/Dockerfile for
# the patched fallback if rod ever regresses. This stage exists only to lift one file:
# the scraper is a single static Go binary, and its image is trixie too, so it runs as-is.
FROM gosom/google-maps-scraper:latest-rod AS gosom

# ── Stage 2: the runtime ───────────────────────────────────────────────────────────────
FROM python:3.12-slim-trixie

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Browsers go to a world-readable path, NOT $HOME. The runtime user is not the build
    # user, and a browser installed into root's home is invisible to uid 999 at run time.
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright \
    # crawl4ai writes its cache under $HOME by default; on a read-only or foreign home
    # that fails at import time rather than at fetch time.
    CRAWL4AI_BASE_DIRECTORY=/tmp/.crawl4ai

# curl for healthchecks/manual fetches; ca-certificates so HTTPS works at all.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# The Google Maps scraper — replaces `docker run`, which the agent cannot do.
COPY --from=gosom /usr/bin/google-maps-scraper /usr/local/bin/google-maps-scraper

# Python deps. crawl4ai pulls playwright; httpx is the CRM/Snov transport.
RUN pip install --no-cache-dir crawl4ai httpx

# THE line that fixes the live blocker. `ldd` on Chromium in the current cloud image
# reports 21 missing shared objects (libglib-2.0.so.0, libnss3, libX11 …); the browser
# installs fine and then dies with exit 127 at launch. These are OS packages, so this
# needs root and cannot be done from inside a running agent.
RUN playwright install-deps chromium \
    && playwright install chromium \
    && chmod -R a+rX /opt/playwright

# The scraping closure. Must be importable as `scripts.<module>`; Rashid's preflight does
# `from scripts.agent_scraping_skill import agent_scraping_skill` and correctly reports
# [WAITING:BLOCKED] when this is absent — which is what the cloud does today.
WORKDIR /app
COPY scripts/ /app/scripts/
RUN test -f /app/scripts/__init__.py || touch /app/scripts/__init__.py
ENV PYTHONPATH=/app

# Mirror the cloud runtime's unprivileged user so a permission problem surfaces HERE,
# in a build we can iterate on, and not on the boss's deploy.
RUN useradd -u 999 -m -s /bin/bash navaiaforge \
    && mkdir -p /app/workspace /tmp/.crawl4ai \
    && chown -R navaiaforge:navaiaforge /app /tmp/.crawl4ai
USER navaiaforge

# Self-check. Proves the four capabilities the PR is responsible for, and — critically —
# proves a LIVE FETCH returns real content. crawl4ai does NOT raise on a failed
# navigation: it returns success=False with markdown=None, which str() renders as the
# literal "None". Trusting the exception is how 7 live sites were recorded as
# "no headcount published" on 2026-07-20. Import success is not fetch success.
COPY deploy/discovery/selfcheck.py /app/selfcheck.py
CMD ["python", "/app/selfcheck.py"]

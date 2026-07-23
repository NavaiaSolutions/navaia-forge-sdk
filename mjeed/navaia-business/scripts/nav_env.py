"""Shared backend-target resolution for NAVAIA workforce scripts.

One knob — NAVAIA_BASE_URL — decides which NavaiaForge backend every *acting*
script targets. The default is the cloud production backend (fareegi), the
single authoritative workforce that does real outreach. Override it only to
point the same scripts at a local Docker stack for prompt iteration, e.g.:

    # PowerShell (this shell only)
    $env:NAVAIA_BASE_URL = "http://localhost:8001"
    # or persist it by adding a line to .env:
    #   NAVAIA_BASE_URL=http://localhost:8001

Resolution order: OS environment first, then the repo .env file, then the
cloud default.
"""
from __future__ import annotations

import os
import re

CLOUD_BASE_URL = "https://fareegi.navaia.sa"
CLOUD_CRM_URL = "https://crm.navaia.sa"  # Twenty CRM, the shared production instance
_DEFAULT_WORKFORCE_ID = "131bb52f-e5eb-44ad-8134-03dc6908b485"  # production NAVAIA Business
_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")


def env(key: str, default: str | None = None) -> str | None:
    """Read a config value: OS env wins, then the repo .env, then `default`."""
    val = os.environ.get(key)
    if val:
        return val
    try:
        text = open(_ENV_PATH).read()
    except FileNotFoundError:
        return default
    m = re.search(rf"^{re.escape(key)}=(.+)$", text, re.M)
    return m.group(1).strip() if m else default


def openrouter_key() -> str | None:
    """THE OpenRouter key. One accessor, so callers cannot disagree about the order.

    `MY_OPENROUTER_KEY` was a second, personal key that went dead on 2026-07-21 (401 on
    every request). Six scripts resolved `MY_OPENROUTER_KEY or OPENROUTER_API_KEY`, so the
    DEAD key won wherever both were set, and every LLM step failed on a credential rather
    than on its own logic. The visible symptom was not an error: the composer fell back to
    library copy and the run looked like it had merely chosen the fallback path.

    The operator commented it out of `.env` on 2026-07-22 and this now reads one name only.
    Resolving a second key here is what created the bug; do not reintroduce a fallback.
    """
    return env("OPENROUTER_API_KEY")


def base_url() -> str:
    """The NavaiaForge backend all acting scripts target (cloud by default)."""
    return env("NAVAIA_BASE_URL", CLOUD_BASE_URL)


def crm_base() -> str:
    """The Twenty CRM instance all acting scripts read/write (cloud by default).

    Was hardcoded as a literal in a dozen scripts; override with NAVAIA_CRM_URL
    (env or .env) so a local/staging CRM can be targeted without editing each one.
    """
    return env("NAVAIA_CRM_URL", CLOUD_CRM_URL)


# The workforce all acting scripts target. Override with NAVAIA_WORKFORCE_ID
# (env or .env) to point the same scripts at another instance — e.g. a local
# stack or a workforce rebuilt elsewhere from the snapshot bundle (its id will
# differ; agents are resolved by NAME, so the roster carries over).
CLOUD_WORKFORCE_ID = env("NAVAIA_WORKFORCE_ID", _DEFAULT_WORKFORCE_ID)

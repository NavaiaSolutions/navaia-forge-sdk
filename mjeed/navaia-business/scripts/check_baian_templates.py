"""Read-only: list Baian WhatsApp templates + Meta approval status.

Dispatches a read-only task to the cloud workforce (Baian is cloud-only) and prints
the agent's template table. Secrets read from .env (BUSINESS_NF). Sends nothing.

Usage:
    python scripts/check_baian_templates.py

See workforce/playbooks/whatsapp_send_baian.md.
"""
from __future__ import annotations

import io
import os
import re
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from navaia_forge import NavaiaForgeClient

import nav_env
CLOUD_BASE = nav_env.base_url()
CLOUD_WF = nav_env.CLOUD_WORKFORCE_ID
TARIQ = "6ba49326-4ec0-4b3b-8651-9526ec96894e"
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")


def _env(key: str) -> str:
    m = re.search(rf"^{re.escape(key)}=(.+)$", open(ENV_PATH).read(), re.M)
    if not m:
        raise SystemExit(f"{key} not found in {ENV_PATH}")
    return m.group(1).strip()


def main() -> None:
    cloud = NavaiaForgeClient(api_key=_env("BUSINESS_NF"), base_url=CLOUD_BASE)
    desc = (
        "READ-ONLY status check. Do NOT send any message, and do NOT create, edit, or "
        "delete anything. Introspect Baian's tools (do not hardcode) and LIST the WhatsApp "
        "templates. Report a table of every template: name, template id, category, language, "
        "and Meta approval status (PENDING / APPROVED / REJECTED). "
        "CRITICAL — LIST EVERY TEMPLATE, DO NOT MISS ANY: the Baian list_templates tool is "
        "NOT paginated and returns only the first page (~13 rows), silently dropping the rest. "
        "You MUST fetch ALL pages: follow Meta's paging.next cursors until there are no more "
        "pages. If the Baian list tool cannot paginate, call Meta's Graph API message_templates "
        "endpoint directly with the configured WABA id + token and page through every cursor. "
        "Do NOT filter by status. State the TOTAL count and confirm you exhausted pagination. "
        "For every template that is REJECTED or otherwise not APPROVED, also report the FULL "
        "rejection detail Meta returned: the rejected_reason code (e.g. INVALID_FORMAT, "
        "ABUSIVE_CONTENT, SCAM, TAG_CONTENT_MISMATCH, PROMOTIONAL), any quality_score / "
        "quality rating, and any human-readable reason or disable_info text. If the tool "
        "returns raw fields, include them verbatim so we can diagnose the cause."
    )
    t = cloud.tasks.create(
        CLOUD_WF,
        "READ-ONLY: Baian template approval status",
        description=desc,
        agent_id=TARIQ,
        priority="standard",
        metadata={"readonly": True},
    )
    print(f"TASK CREATED: {t.id} | status: {t.status}")
    deadline = time.time() + 180
    last = None
    while time.time() < deadline:
        t = cloud.tasks.get(t.id)
        if t.status != last:
            print(f"  status -> {t.status}")
            last = t.status
        s = str(t.status).lower()
        if "waiting_plan" in s:
            cloud.tasks.approve(t.id)
            print("  approved plan")
        elif s in ("done", "failed", "cancelled", "waiting_blocked", "waiting_question"):
            break
        time.sleep(6)
    t = cloud.tasks.get(t.id)
    print(f"\n=== FINAL: {t.status} ===")
    print((t.result or "")[:5000])


if __name__ == "__main__":
    main()

"""Send a WhatsApp message via Baian (cloud-only) — canonical, proven flow.

Baian's token lives only in the cloud, so the send runs as a task on the cloud
workforce assigned to Tariq (SDR). First-contact WhatsApp needs a Meta-APPROVED
template; pass its name with --template (check status with check_baian_templates.py).

Secrets are read from .env (BUSINESS_NF, MY_PHONE) — nothing hardcoded.

Usage:
    python scripts/baian_send.py --template navaia_connectivity_test_v1
    python scripts/baian_send.py --to +9665XXXXXXXX --template <approved_template>

See workforce/playbooks/whatsapp_send_baian.md for the full SOP.
"""
from __future__ import annotations

import argparse
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
    ap = argparse.ArgumentParser(description="Send a WhatsApp via Baian (cloud task).")
    ap.add_argument("--template", required=True, help="Name of an APPROVED Meta template.")
    ap.add_argument("--to", default=None, help="Recipient E.164 number (default: MY_PHONE from .env).")
    ap.add_argument("--vars-file", default=None,
                    help="JSON file with the array of template variables ({{1}}..{{n}}, in order) "
                         "— passed to the agent VERBATIM. Without it the agent fills placeholders "
                         "(test-only; never for real leads).")
    ap.add_argument("--timeout", type=int, default=210, help="Seconds to poll for completion.")
    args = ap.parse_args()

    key = _env("BUSINESS_NF")
    to = args.to or _env("MY_PHONE")
    cloud = NavaiaForgeClient(api_key=key, base_url=CLOUD_BASE)

    if args.vars_file:
        import json
        tpl_vars = json.load(open(args.vars_file, encoding="utf-8"))
        fill_step = ("2. Fill the template variables EXACTLY with these values, in this order — "
                     "pass them VERBATIM, do not change, translate, or shorten a single character:\n"
                     + json.dumps(tpl_vars, ensure_ascii=False, indent=1))
    else:
        fill_step = "2. Fill any required variables with a minimal sensible value; if none, send as-is."

    desc = f"""Send ONE WhatsApp message via the Baian integration to {to} (authorized recipient).

Use the ALREADY-APPROVED Meta template `{args.template}` — do NOT create or wait on any template. Steps:
1. Introspect Baian's tools (do not hardcode endpoints). Inspect `{args.template}` for any required body/parameter variables.
{fill_step}
3. Send via Baian's send_template tool to {to}. Send to this number ONLY. Do NOT look up CRM leads, do NOT start a sequence, do NOT message anyone else.
4. FALLBACK — if Baian's tool errors (e.g. Graph API 404 on a phone-number id): send via the
   direct Graph API instead (the proven workaround; never trust a cached phone-number id):
   a. Read WABA_ID from env NF_BAIAN_WABA_ID and the token from env NF_BAIAN_META_TOKEN.
   b. DISCOVER the current phone number id: GET https://graph.facebook.com/v24.0/{{WABA_ID}}/phone_numbers
      (Authorization: Bearer token) — take the id from the response.
   c. POST https://graph.facebook.com/v24.0/{{PHONE_NUMBER_ID}}/messages with
      {{"messaging_product":"whatsapp","to":"{to}","type":"template",
        "template":{{"name":"{args.template}","language":{{"code":"ar"}},
        "components":[{{"type":"body","parameters":[…]}}]}}}}.
Report: template used, variables filled, the message_id (wamid.…), which path worked (Baian tool
or direct Graph), the exact final text delivered, and any error. Do not fake success."""

    t = cloud.tasks.create(
        CLOUD_WF,
        f"SEND: WhatsApp via Baian ({args.template})",
        description=desc,
        agent_id=TARIQ,
        priority="standard",
        metadata={"channel": "whatsapp", "template": args.template},
    )
    print(f"TASK CREATED: {t.id} | status: {t.status}")

    deadline = time.time() + args.timeout
    last = None
    while time.time() < deadline:
        t = cloud.tasks.get(t.id)
        if t.status != last:
            print(f"  status -> {t.status}")
            last = t.status
        s = str(t.status).lower()
        if "waiting_plan" in s:
            # approve REQUIRES a JSON body — the SDK's bodyless approve() returns 422.
            cloud.tasks._http.post(f"/tasks/{t.id}/approve", {})
            print("  approved plan")
        elif s in ("done", "failed", "cancelled", "waiting_blocked", "waiting_question"):
            break
        time.sleep(6)

    t = cloud.tasks.get(t.id)
    print(f"\n=== FINAL: {t.status} ===")
    print((t.result or "")[:4500])


if __name__ == "__main__":
    main()

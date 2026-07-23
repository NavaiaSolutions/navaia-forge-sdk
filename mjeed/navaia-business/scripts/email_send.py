"""Send a single email via the Zoho Mail integration (transactional / test sends).

Bulk outreach goes through a Snov.io campaign (see workforce/playbooks/email_send_snov.md);
this is for one-off / test / transactional emails. Dispatches a cloud task to Tariq, who
uses the Zoho integration's send tool. The agent is told NOT to add a signature — the Zoho
domain signature is appended server-side. Key read from .env (BUSINESS_NF).

Usage:
    python scripts/email_send.py --to x@y.com --subject "Hi" --body "..."
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
import time
import traceback

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from navaia_forge import NavaiaForgeClient

import nav_env
CLOUD_BASE = nav_env.base_url()
CLOUD_WF = nav_env.CLOUD_WORKFORCE_ID
TARIQ = "6ba49326-4ec0-4b3b-8651-9526ec96894e"
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")


def _env(key: str) -> str:
    m = re.search(rf"^{re.escape(key)}=(.+)$", open(ENV_PATH).read(), re.M)
    if not m:
        raise SystemExit(f"{key} not found in .env")
    return m.group(1).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", required=True)
    ap.add_argument("--subject", required=True)
    ap.add_argument("--body", required=True)
    ap.add_argument("--signature-file", help="Path to an HTML signature file to append.")
    ap.add_argument("--html", action="store_true", help="Send the body as HTML.")
    ap.add_argument("--via", choices=["zoho", "snov"], default="zoho", help="Send transport.")
    args = ap.parse_args()

    cloud = NavaiaForgeClient(api_key=_env("BUSINESS_NF"), base_url=CLOUD_BASE)

    sig = ""
    if args.signature_file:
        sig = open(args.signature_file, encoding="utf-8").read().strip()
    as_html = args.html or bool(sig)

    # Fail closed on the plain-text/HTML mismatch. A body with tags sent as text/plain arrives
    # with the markup VISIBLE — literal <div>/<br> in a stranger's inbox under the operator's
    # name. The old code sent it silently; make the operator choose instead of guessing wrong.
    if not as_html and re.search(r"<(?:/?[a-zA-Z][a-zA-Z0-9]*|br\s*/?)\b[^>]*>", args.body):
        raise SystemExit(
            "Body looks like HTML but would be sent as plain text — the tags would show as\n"
            "literal markup in the recipient's inbox. Pass --html to render it, or strip the\n"
            "tags if you really mean to send plain text."
        )
    transport = "Snov.io" if args.via == "snov" else "Zoho Mail"

    parts = [
        f"Send ONE email via the {transport} integration to {args.to} (authorized recipient). Single transactional/test send.",
        f"- Subject: {args.subject}",
    ]
    if args.via == "snov":
        parts.append("- Use the Snov.io integration to send (a single-recipient send / minimal 1-person campaign). If Snov can only enrich/verify and cannot SEND email from this workforce, say so explicitly and STOP — do not fall back to another transport.")
    else:
        parts.append("- Use the Zoho Mail integration's send tool.")
    if as_html:
        parts.append(f"- Send as an HTML email (text/html) so formatting renders.\n- Body HTML (exactly this): {args.body}")
    else:
        parts.append(f"- Body (exactly this, plain text): {args.body}")
    if sig:
        parts.append("- Append EXACTLY this HTML signature after the body, unchanged — do not edit, reformat, translate, or add anything of your own:\n" + sig)
    else:
        parts.append("- Do NOT add any signature/footer of your own.")
    parts.append("- Introspect the send tool (do not hardcode). Send to this ONE address only. Do NOT look up CRM leads, do NOT start a sequence.")
    parts.append("Report: the exact tool/integration used, the send result/message id, whether it was sent as HTML, and whether the signature was included.")
    desc = "\n".join(parts)

    t = cloud.tasks.create(
        CLOUD_WF, f"EMAIL ({args.via}): {args.subject}",
        description=desc, agent_id=TARIQ, priority="standard",
        metadata={"channel": "email", "transport": args.via},
    )
    print(f"TASK CREATED: {t.id} | status: {t.status}")
    deadline = time.time() + 200
    last = None
    while time.time() < deadline:
        t = cloud.tasks.get(t.id)
        if t.status != last:
            print(f"  status -> {t.status}")
            last = t.status
        s = str(t.status).lower()
        if "waiting_plan" in s:
            try:
                cloud.tasks.approve(t.id)
                print("  approved plan")
            except Exception:
                traceback.print_exc()
        elif s in ("done", "failed", "cancelled", "waiting_blocked", "waiting_question"):
            break
        time.sleep(6)
    t = cloud.tasks.get(t.id)
    print(f"\n=== FINAL: {t.status} ===")
    print((t.result or "")[:4000])


if __name__ == "__main__":
    main()

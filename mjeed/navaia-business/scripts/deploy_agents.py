"""Deploy the 7 agents' full instructions to the cloud workforce (IN-PLACE UPDATE).

Reads each agent's `### system_prompt (deploy payload)` block from
workforce/agents/*.md and PUTs it onto the matching EXISTING cloud agent
(matched by name). It never creates, renames, or deletes agents — the fixed
7-agent roster is untouched. Key read from .env (BUSINESS_NF); nothing hardcoded.

Usage:
    python scripts/deploy_agents.py              # deploy all 7
    python scripts/deploy_agents.py --only Ahmed,Tariq,Lina   # subset
    python scripts/deploy_agents.py --dry-run    # show what would change, write nothing

See workforce/playbooks/deploy_and_sync.md.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
import traceback

# Only re-wrap when stdout is NOT already UTF-8. Wrapping unconditionally re-wrapped an
# existing wrapper (e.g. under PYTHONIOENCODING=utf-8), and the discarded one was garbage
# collected — closing the underlying buffer, so the first print died with
# "ValueError: I/O operation on closed file" and the deploy never ran. Same guard as
# snov_preview.py. line_buffering keeps progress visible when output is piped to a file.
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace", line_buffering=True)

from navaia_forge import NavaiaForgeClient

import nav_env
CLOUD_BASE = nav_env.base_url()
CLOUD_WF = nav_env.CLOUD_WORKFORCE_ID
ROOT = os.path.join(os.path.dirname(__file__), "..")
AGENTS_DIR = os.path.join(ROOT, "workforce", "agents")
SHARED_FILE = "_shared_preamble.md"  # prepended to every agent's role block

FILES = {
    "Ahmed": "ahmed_gm_orchestrator.md",
    "Tariq": "tariq_sdr_sender.md",
    "Lina": "lina_marketing.md",
    "Ghida": "ghida_creative.md",
    "Nora": "nora_scorer.md",
    "Rashid": "rashid_scraper.md",
    "Fahad": "fahad_account_manager.md",
}


def _env(key: str) -> str:
    m = re.search(rf"^{re.escape(key)}=(.+)$", open(os.path.join(ROOT, ".env")).read(), re.M)
    if not m:
        raise SystemExit(f"{key} not found in .env")
    return m.group(1).strip()


def _extract_block(fname: str, header: str) -> str | None:
    text = open(os.path.join(AGENTS_DIR, fname), encoding="utf-8").read()
    m = re.search(rf"###\s*{re.escape(header)} \(deploy payload\)\s*\n+```[a-zA-Z]*\n(.*?)\n```", text, re.S)
    return m.group(1).strip() if m else None


def extract_prompt(fname: str) -> str | None:
    """Compose the shipped system prompt: shared preamble + this agent's role block."""
    role = _extract_block(fname, "system_prompt")
    if role is None:
        return None
        
    # Dynamic template injection for Lina
    if "{{OUTREACH_TEMPLATES_INJECTED_HERE}}" in role:
        try:
            templates_path = os.path.join(ROOT, "workforce", "04_outreach_templates.md")
            with open(templates_path, encoding="utf-8") as tf:
                role = role.replace("{{OUTREACH_TEMPLATES_INJECTED_HERE}}", tf.read())
        except Exception as e:
            print(f"!! Warning: Could not inject templates: {e}")

    shared = _extract_block(SHARED_FILE, "shared_preamble")
    if not shared:
        print(f"!! {SHARED_FILE}: no shared_preamble block found — shipping role block only")
        return role
    prompt = f"{shared}\n\n{role}"

    # The operator's contact number is injected HERE rather than written in the file: the
    # repo is mirrored into a PUBLIC SDK repo and that is a personal line. The deployed
    # prompt still carries the real number, because an agent that does not know it would
    # either omit the contact or — far worse — invent one.
    #
    # Refuse rather than ship the placeholder: a prompt reading "Contact: {{CONTACT_PHONE}}"
    # would put that literal string in front of a prospect.
    if "{{CONTACT_PHONE}}" in prompt:
        phone = nav_env.env("NAVAIA_CONTACT_PHONE")
        if not phone:
            raise SystemExit(
                "NAVAIA_CONTACT_PHONE is not set, and the shared preamble expects it. "
                "Set it in .env — deploying would put the literal '{{CONTACT_PHONE}}' "
                "into a prompt that is read out to prospects.")
        prompt = prompt.replace("{{CONTACT_PHONE}}", phone.strip())
    return prompt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="Comma-separated agent names (default: all 7).")
    ap.add_argument("--dry-run", action="store_true", help="Show changes, write nothing.")
    args = ap.parse_args()

    wanted = [n.strip() for n in args.only.split(",")] if args.only else list(FILES)

    # Refuse to deploy a malformed prompt. On 2026-07-22 a lost closing fence made
    # extract_prompt sweep 39,903 chars of document prose into Lina's payload, including
    # copy for two RETIRED verticals — and reported success. A prompt defect is invisible
    # in the dashboard until an agent misbehaves in a live run against real businesses,
    # so the gate belongs here rather than in a habit of remembering to run the checker.
    import check_agent_prompts
    if (problems := check_agent_prompts.check()):
        print("REFUSING TO DEPLOY — prompt validation failed:")
        for p in problems:
            print(f"  !! {p}")
        raise SystemExit(1)

    cloud = NavaiaForgeClient(api_key=_env("BUSINESS_NF"), base_url=CLOUD_BASE)
    agents = {a.name: a for a in cloud.agents.list(workforce_id=CLOUD_WF)}

    for name in wanted:
        a = agents.get(name)
        if not a:
            print(f"!! {name}: no cloud agent found — skipping")
            continue
        prompt = extract_prompt(FILES[name])
        if not prompt:
            print(f"!! {name}: no deploy-payload block in {FILES[name]} — skipping")
            continue
        old = getattr(a, "system_prompt", None) or getattr(a, "instructions", None) or ""
        if args.dry_run:
            print(f"DRY  {name}: {len(old)} -> {len(prompt)} chars (no write)")
            continue
        try:
            cloud.agents.update(a.id, instructions=prompt)
            print(f"OK   {name}: {len(old)} -> {len(prompt)} chars")
        except Exception:
            print(f"!! {name}: update FAILED")
            traceback.print_exc()

    if not args.dry_run:
        print("\n=== verify (re-fetch) ===")
        for name in wanted:
            if name in agents:
                a = cloud.agents.get(agents[name].id)
                sp = getattr(a, "system_prompt", None) or getattr(a, "instructions", None) or ""
                print(f"{name}: now {len(sp)} chars | {sp[:60]!r}")


if __name__ == "__main__":
    main()

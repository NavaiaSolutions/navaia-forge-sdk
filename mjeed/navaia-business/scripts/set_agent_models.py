"""Apply the cost policy to the cloud workforce's agents (IN-PLACE).

Sets, per agent, the SDK-native cost levers:
  - model_name       : cheap default
  - escalation_model : ceiling the runtime escalates to only when needed
  - max_turns        : turn cap (each turn is a paid model round-trip)

Policy: kimi-k2.6 is the ceiling. Everyone defaults to the cheap model with kimi as the
escalation target — EXCEPT Lina (customer-facing Arabic copy), who stays on kimi primary
so quality never depends on the escalation trigger. In-place `agents.update` only; never
creates/removes agents. Key read from .env (BUSINESS_NF).

Usage:
    python scripts/set_agent_models.py            # apply
    python scripts/set_agent_models.py --dry-run  # show, write nothing
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
import traceback

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from navaia_forge import NavaiaForgeClient

import nav_env
CLOUD_BASE = nav_env.base_url()
CLOUD_WF = nav_env.CLOUD_WORKFORCE_ID
ROOT = os.path.join(os.path.dirname(__file__), "..")

# PRE-DEPLOYMENT policy (directive 2026-07-09): base = cheap qwen, ceiling = kimi as the
# native escalation target (runtime escalates only when needed). The higher PRODUCTION tier
# (kimi FLOOR -> frontier escalation, e.g. claude-opus-4.8) is applied separately just before
# deployment — see the boss directive. This is the standard OPTIMIZATION.md rung-1 -> rung-2 cascade.
BASE = "qwen/qwen3.6-plus"        # cheap default (rung 1) for ALL agents
ESCALATION = "moonshotai/kimi-k2.6"  # ceiling (rung 2) — runtime escalates only when needed

MAX_TURNS = 25
POLICY = {
    name: {"model_name": BASE, "escalation_model": ESCALATION, "max_turns": MAX_TURNS}
    for name in ["Ahmed", "Tariq", "Lina", "Ghida", "Nora", "Rashid", "Fahad"]
}


def _env(key: str) -> str:
    m = re.search(rf"^{re.escape(key)}=(.+)$", open(os.path.join(ROOT, ".env")).read(), re.M)
    if not m:
        raise SystemExit(f"{key} not found in .env")
    return m.group(1).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cloud = NavaiaForgeClient(api_key=_env("BUSINESS_NF"), base_url=CLOUD_BASE)
    agents = {a.name: a for a in cloud.agents.list(workforce_id=CLOUD_WF)}

    for name, fields in POLICY.items():
        a = agents.get(name)
        if not a:
            print(f"!! {name}: no cloud agent found — skipping")
            continue
        summary = f"{fields['model_name']} | esc={fields.get('escalation_model')} | max_turns={fields['max_turns']}"
        if args.dry_run:
            print(f"DRY  {name}: -> {summary}")
            continue
        try:
            cloud.agents.update(a.id, **fields)
            print(f"OK   {name}: -> {summary}")
        except Exception:
            print(f"!! {name}: update FAILED")
            traceback.print_exc()

    if not args.dry_run:
        print("\n=== verify (re-fetch) ===")
        for name in POLICY:
            if name in agents:
                a = cloud.agents.get(agents[name].id)
                print(f"{name}: model={a.model_name} | esc={getattr(a, 'escalation_model', None)} | max_turns={getattr(a, 'max_turns', None)}")


if __name__ == "__main__":
    main()

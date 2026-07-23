#!/usr/bin/env python3
"""Validate the agent system prompts BEFORE they are deployed.

    python scripts/check_agent_prompts.py

Exits non-zero if any agent's deploy payload is malformed or has lost a functional
invariant. Run it before `deploy_agents.py`; a bad prompt is not visible in the cloud
dashboard until an agent misbehaves in a live run.

## Why this exists

On 2026-07-22 Lina's payload was found CORRUPTED: a truncated `<follow_ups>` tag had eaten
the closing fence, so `deploy_agents.extract_prompt` ran past the payload and swept in
document prose, markdown headings, retired-vertical templates and Meta submission
instructions — 39,903 characters of shipped system prompt, most of it not instructions at
all. Nothing reported it. The extraction "succeeded" and deployed happily.

That is the failure mode this guards: the payload is defined by a fence, a fence is one
character, and losing it fails silently and expensively. Every check below is something
that was actually wrong at some point, not a hypothetical.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import deploy_agents

# A prompt is instructions, not documentation. These ceilings are generous against the
# refactored sizes (~1,500-2,200 tokens each) and exist to catch a re-run of the Lina
# corruption, where the payload silently absorbed a whole document.
MAX_CHARS = 12000

# Literals whose LOSS changes behaviour silently rather than loudly. A missing route
# marker does not error — the chain simply dies and nobody is told (2026-07-19 incident).
REQUIRED: dict[str, tuple[str, ...]] = {
    "Ahmed": ("[route:rashid]", "[route:lina]", "[DONE]"),
    "Rashid": ("scripts/discover.py", "[route:ahmed]", "[WAITING:BLOCKED]"),
    # The three ACTIVE template names: Tariq sends whatever name Lina hands him, so a typo
    # here reaches Meta as an unknown template and the send fails per lead.
    "Lina": ("[route:tariq]", "navaia_mj_realestate_t1", "navaia_mj_contracting_t1_v2",
             "navaia_mj_training_t1_v2", "{{1}}", "{{5}}"),
    # The gate marker, and the handoff field names Lina must fill and Tariq must consume.
    "Tariq": ("[WAITING:QUESTION]", "[route:ahmed]", "RESULT", "wa_template",
              "wa_variables", "pain_block", "subject_line"),
    "Nora": ("[DONE]", "[WAITING:BLOCKED]"),
    "Ghida": ("[route:ahmed]",),
    "Fahad": ("[route:ahmed]",),
}

# Present in the shared preamble, therefore present in EVERY composed prompt. If the shared
# block stops being prepended, all seven agents lose the runtime contract at once.
SHARED_REQUIRED = ("[WAITING:BLOCKED]", "[route:", "createdBy", "Real Estate",
                   "Contracting & Facilities", "Training Institutes")

# Retired verticals must not reappear in any prompt: an agent that still knows the clinics
# template will use it when a lead looks like a clinic.
FORBIDDEN = ("navaia_mj_clinics_t1", "navaia_mj_finance_t1_v2",
             "{{OUTREACH_TEMPLATES_INJECTED_HERE}}")


def check() -> list[str]:
    problems: list[str] = []
    for name, fname in deploy_agents.FILES.items():
        prompt = deploy_agents.extract_prompt(fname)
        if not prompt:
            problems.append(f"{name}: no deploy payload extracted from {fname}")
            continue

        # Structural: these can only appear if the fence was lost and prose leaked in.
        if "```" in prompt:
            problems.append(f"{name}: a code fence leaked into the payload — "
                            f"the block in {fname} is not closed")
        if "\n##" in prompt:
            problems.append(f"{name}: a markdown heading leaked into the payload — "
                            f"the block in {fname} is not closed")
        if len(prompt) > MAX_CHARS:
            problems.append(f"{name}: payload is {len(prompt)} chars (max {MAX_CHARS}) — "
                            f"a prompt instructs, it does not document")

        for lit in REQUIRED.get(name, ()) + SHARED_REQUIRED:
            if lit not in prompt:
                problems.append(f"{name}: missing required literal {lit!r}")
        for lit in FORBIDDEN:
            if lit in prompt:
                problems.append(f"{name}: contains forbidden literal {lit!r}")

        # Route markers are matched literally and are case-sensitive; a miscased one
        # matches no edge and dies without a word. Only a marker naming a REAL agent is a
        # defect — the preamble teaches the rule with `[ROUTE:NAME]` as a counter-example,
        # and that placeholder names nobody, so it can never fire.
        for agent in deploy_agents.FILES:
            for bad in (f"[ROUTE:{agent.upper()}]", f"[Route:{agent}]"):
                if bad in prompt:
                    problems.append(f"{name}: {bad!r} matches no edge — must be lowercase")
    return problems


def main() -> int:
    problems = check()
    for name, fname in deploy_agents.FILES.items():
        p = deploy_agents.extract_prompt(fname) or ""
        print(f"  {name:8} {len(p):6} chars  ~{len(p)//4:5} tokens")
    if problems:
        print(f"\n{len(problems)} PROBLEM(S):")
        for p in problems:
            print(f"  !! {p}")
        return 1
    print(f"\nAll {len(deploy_agents.FILES)} prompts OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

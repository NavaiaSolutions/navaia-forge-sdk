#!/usr/bin/env python3
"""
NAVAIA pipeline console — the ONE interactive script for the operator.
No LLM, no CLI agent on this machine: it fires cloud batch tasks and lets you
answer their HITL approval gates from this terminal.

    .venv/Scripts/python.exe scripts/run_pipeline.py

What it does (menu):
  1. Fire the next lead batch  — picks unsubmitted leads from the pool
     (leads_scraped_compact.json), submits a pipeline task to Ahmed (GM),
     then watches it and lets you approve/answer when it pauses.
  2. Run outreach for leads already in the CRM (leadStatus="Not Contacted") —
     no new leads needed; Lina writes, you approve, Tariq sends.
  3. Watch / approve an existing task (paste a task id, or pick from the
     recent list) — e.g. one that is already waiting on you.

Approval contract (see workforce/HANDOFF.md + memory): a waiting task is
answered via POST /tasks/{id}/approve with body {"response": "<your text>"} —
a bare approve delivers no text and the agent just re-asks.

Refill the pool when it runs dry (needs Docker, see playbooks/lead_pipeline.md):
  docker run --rm -v "$PWD:/work" gosom/google-maps-scraper:latest-rod \\
      -input /work/queries.txt -results /work/leads_raw.csv -depth 3 -c 2 \\
      -geo "24.7136,46.6753" -lang ar -zoom 12 -exit-on-inactivity 3m
  python scripts/distill_scraped_leads.py leads_raw.csv leads_scraped_compact.json
"""
from __future__ import annotations

import io
import json
import os
import sys
import time

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nav_env
from navaia_forge import NavaiaForgeClient
from submit_lead_batch import ALL_VERTICALS, ROOT, build_outreach_task, resolve_agent, submit_batch

WAITING = ("waiting_question", "waiting_plan", "waiting_blocked")
TERMINAL = ("done", "failed", "cancelled")
POLL_SECONDS = 20

cloud = NavaiaForgeClient(api_key=nav_env.env("BUSINESS_NF"), base_url=nav_env.base_url())


def ask(prompt: str, default: str = "") -> str:
    raw = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return raw or default


def choose_verticals(default: list[str]) -> list[str] | None:
    """Numbered vertical picker. Enter = default, 'a' = all, e.g. '1,3' = subset."""
    print("Verticals:")
    for i, v in enumerate(ALL_VERTICALS, 1):
        mark = "*" if v in default else " "
        print(f"  {i}. {v} {mark}")
    hint = "Enter = *default, a = all, or numbers like 1,3"
    raw = input(f"Pick ({hint}): ").strip().lower()
    if not raw:
        return default
    if raw in ("a", "all"):
        return list(ALL_VERTICALS)
    picked = []
    for part in raw.replace(" ", "").split(","):
        if not part.isdigit() or not 1 <= int(part) <= len(ALL_VERTICALS):
            print(f"Invalid choice {part!r} — use numbers 1-{len(ALL_VERTICALS)}.")
            return None
        v = ALL_VERTICALS[int(part) - 1]
        if v not in picked:
            picked.append(v)
    return picked


def answer_task(task_id: str, text: str) -> bool:
    """Deliver the operator's answer. Body is REQUIRED (bodyless approve -> 422)."""
    try:
        cloud.tasks._http.post(f"/tasks/{task_id}/approve", {"response": text})
        return True
    except Exception as e:
        print(f"  ✗ approve failed: {e}")
        return False


def show_waiting(task) -> None:
    print("\n" + "═" * 70)
    print("⏸  THE TASK IS WAITING ON YOU — here is what it asks/proposes:")
    print("═" * 70)
    print((task.result or "(no text)").strip())
    print("═" * 70)


def watch(task_id: str) -> None:
    """Poll until terminal; on a waiting state, prompt for the answer inline.

    Uses the raw task JSON because it carries a `logs` array of lifecycle
    events (submitted / started / waiting / completed / failed) that the SDK
    model drops — each new event is printed as it lands. The backend does not
    expose step-level agent activity (tool calls etc.); this is as live as the
    API allows.
    """
    print(f"\nWatching task {task_id} (poll every {POLL_SECONDS}s, Ctrl+C to stop watching)…")
    last = None
    seen_logs: set[str] = set()
    while True:
        try:
            raw = cloud.tasks._http.get(f"/tasks/{task_id}")
            t = cloud.tasks.get(task_id)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"  poll error ({e}); retrying…")
            time.sleep(POLL_SECONDS)
            continue
        for ev in (raw.get("logs") or []):
            eid = ev.get("id") or f"{ev.get('event')}@{ev.get('created_at')}"
            if eid not in seen_logs:
                seen_logs.add(eid)
                ts = (ev.get("created_at") or "")[11:19]
                print(f"  [{ts}] {ev.get('event')}: {ev.get('detail') or ''}")
        status = str(t.status).lower()
        if status != last:
            print(f"  [{time.strftime('%H:%M:%S')}] status = {status}")
            last = status

        if status in ("waiting_question", "waiting_plan"):
            show_waiting(t)
            print("Reply options:  a = approve as proposed   |  type your own answer text")
            print("                s = skip/park (keep waiting, stop watching)")
            choice = input("> ").strip()
            if choice.lower() == "s" or not choice:
                print("Left waiting — rerun the console later to answer.")
                return
            text = "APPROVED — proceed exactly as proposed." if choice.lower() == "a" else choice
            # Confirm before delivering — a stray keystroke must never become the answer.
            if input(f'Deliver this answer: "{text}" ? (y/N) ').strip().lower() != "y":
                print("Not delivered.")
                continue
            if answer_task(task_id, text):
                print("  ✓ answer delivered; task resumes…")
                last = None
        elif status == "waiting_blocked":
            show_waiting(t)
            print("This task is BLOCKED (cannot be answered — backend only allows re-run).")
            print("Options:  r = re-run it as a fresh task (same description)   |  Enter = stop watching")
            if input("> ").strip().lower() == "r":
                try:
                    cloud.tasks.reject(task_id, "re-run after blocked")
                except Exception:
                    pass
                nt = cloud.tasks.create(nav_env.CLOUD_WORKFORCE_ID, t.title,
                                        description=t.description, agent_id=t.agent_id,
                                        priority="high")
                print(f"  ✓ re-created as {nt.id}")
                watch(nt.id)
            return
        elif status in TERMINAL:
            print("\n" + "─" * 70)
            print(f"Task ended: {status.upper()}")
            print((t.result or "(no result text)").strip()[:4000])
            print("─" * 70)
            return
        time.sleep(POLL_SECONDS)


def fire_batch() -> None:
    pool_file = os.path.join(ROOT, "leads_scraped_compact.json")
    if not os.path.exists(pool_file):
        print("No lead pool (leads_scraped_compact.json). Scrape + distill first — see the header.")
        return
    vlist = choose_verticals(default=["Real Estate", "Contracting & Facilities"])
    if vlist is None:
        return
    per = int(ask("Qualified target per vertical", "15"))
    task_id = submit_batch(vlist, per, pool_file)
    if task_id:
        watch(task_id)


def fire_outreach_existing() -> None:
    """Standing loop over CRM leads that were imported but never contacted.
    Deterministic prep (field normalization + Snov email enrichment) runs HERE,
    locally, before the task exists — the cloud only fills templates, gates, sends."""
    verticals = choose_verticals(default=list(ALL_VERTICALS))
    if verticals is None:
        return
    print("\nPrep (local, deterministic):")
    built = build_outreach_task(verticals)
    if built is None:
        print("No Not Contacted leads in those verticals — nothing to send.")
        return
    title, desc = built
    task = cloud.tasks.create(
        nav_env.CLOUD_WORKFORCE_ID, title, description=desc,
        agent_id=resolve_agent(cloud, "Ahmed"), priority="high",
        metadata={"kind": "outreach_existing", "approval_gate": "hitl_any_channel",
                  "verticals": verticals},
    )
    print(f"✓ Task {task.id} submitted ({task.status}).")
    watch(task.id)


APPROVE_ALL_TEXT = (
    "Approve all — send to every rendered lead exactly as shown, nothing altered. "
    "THE GATE IS NOW ANSWERED: do NOT re-render the messages, do NOT ask again, do NOT "
    "output [WAITING:QUESTION] again. Go DIRECTLY to the SEND step of your task: end your "
    "output with the COMPACT SEND MANIFEST (per-lead one-liners: person_id | company | "
    "phone | email-or-'-' | vertical | WA template name | {{1}}..{{5}} values | email "
    "tokens — never full rendered bodies) followed by the literal marker [ROUTE:TARIQ] "
    "on its own line."
)


def approve_all_waiting() -> None:
    """One keypress for every open gate: list all waiting tasks, confirm ONCE, answer each."""
    try:
        tasks = cloud.tasks.list(workforce_id=nav_env.CLOUD_WORKFORCE_ID)
    except Exception as e:
        print(f"(couldn't list tasks: {e})")
        return
    waiting = [t for t in tasks if str(t.status).lower() in ("waiting_question", "waiting_plan")]
    if not waiting:
        print("No tasks are waiting on you right now.")
        return
    print(f"\n{len(waiting)} task(s) waiting on you:")
    for i, t in enumerate(waiting, 1):
        print(f"  {i}. [{str(t.status).lower():16}] {t.title[:70]}  ({t.id[:8]}…)")
        tail = (t.result or "").strip()
        if tail:
            print(f"      …{tail[-160:].replace(chr(10), ' ')}")
    if input(f'\nApprove ALL {len(waiting)} as rendered? This SENDS real messages. (yes/N) ').strip().lower() != "yes":
        print("Nothing approved.")
        return
    for t in waiting:
        ok = answer_task(t.id, APPROVE_ALL_TEXT)
        print(f"  {'✓' if ok else '✗'} {t.title[:60]} ({t.id[:8]}…)")
    print("All open gates answered — the tasks resume and route their sends to Tariq.")


def pick_existing() -> None:
    try:
        tasks = cloud.tasks.list(workforce_id=nav_env.CLOUD_WORKFORCE_ID)
        recent = sorted(tasks, key=lambda t: str(getattr(t, "created_at", "")), reverse=True)[:10]
        for i, t in enumerate(recent, 1):
            print(f"  {i}. [{str(t.status).lower():17}] {t.title[:70]}  ({t.id[:8]}…)")
        raw = ask("Number to watch, or paste a full task id")
        task_id = recent[int(raw) - 1].id if raw.isdigit() and 1 <= int(raw) <= len(recent) else raw
    except Exception as e:
        print(f"(couldn't list tasks: {e})")
        task_id = ask("Paste the task id")
    if task_id:
        watch(task_id)


def main() -> None:
    print(f"NAVAIA pipeline console — backend {nav_env.base_url()}")
    while True:
        print("\n1) Fire next lead batch (scraped pool → full pipeline)"
              "\n2) Outreach for existing CRM leads (Not Contacted)"
              "\n3) Watch / approve an existing task"
              "\n4) Approve ALL waiting gates at once"
              "\nq) Quit")
        choice = input("> ").strip().lower()
        try:
            if choice == "1":
                fire_batch()
            elif choice == "2":
                fire_outreach_existing()
            elif choice == "3":
                pick_existing()
            elif choice == "4":
                approve_all_waiting()
            elif choice in ("q", "quit", "exit"):
                return
        except KeyboardInterrupt:
            print("\n(stopped watching — task keeps running in the cloud)")


if __name__ == "__main__":
    main()

"""Telegram workforce bot (local stopgap) — full control of the cloud workforce from your phone.

Supersedes telegram_approval_bridge.py. A persistent local process that bridges Telegram
<-> the CLOUD workforce API (fareegi). Gives menus + inline buttons for:
  - Assign tasks / ask agents, with HUMAN-IN-THE-LOOP approval: when a task pauses on
    waiting_plan / waiting_question / waiting_blocked, you get ✅ Approve / ❌ Reject buttons.
  - Chat mode: a real back-and-forth conversation with an agent (conversations API).
  - Approvals view: every pending waiting/blocked task, each with approve/reject buttons.
  - Approve outreach sends (each approval shows COMPANY INFO + a verify link first).
  - Status (recent cloud tasks) / Daily report (Rashid).
On a successful send it sets the lead's CRM leadStatus = WhatsApped.

Only ONE process may poll a bot token — stop the local backend bot first
(`docker stop navaia-forge-api`). This is the LOCAL stopgap (needs your machine on);
cloud Telegram via Navaia is the always-on version.

Secrets from .env (business repo, fallback SDK repo): BUSINESS_NF, TELEGRAM_BOT_TOKEN,
TELEGRAM_CHAT_ID, MY_PHONE, TWENTY_TOKEN. Nothing hardcoded.

Send mode (TEST vs LIVE) is a RUNTIME toggle — flip it from Telegram itself
(🔀 Send mode button or /mode), no restart needed. --to-me only sets the STARTING mode.

Usage:
    python scripts/telegram_workforce_bot.py            # starts LIVE (sends to real leads on approval)
    python scripts/telegram_workforce_bot.py --to-me    # starts in TEST (approvals send to YOUR number)
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
import threading
import time
import urllib.parse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import httpx
from navaia_forge import NavaiaForgeClient

import nav_env
CLOUD_BASE = nav_env.base_url()
CLOUD_WF = nav_env.CLOUD_WORKFORCE_ID
TARIQ = "6ba49326-4ec0-4b3b-8651-9526ec96894e"
CRM_BASE = nav_env.crm_base()
BIZ_ENV = os.path.join(os.path.dirname(__file__), "..", ".env")
SDK_ENV = r"C:\Users\aabbo\navaia-forge-sdk\.env"

WAITING_STATES = ("waiting_plan", "waiting_question", "waiting_blocked")
DONE_STATES = ("done", "failed", "cancelled")
STATUS_ICON = {"done": "✅", "failed": "❌", "cancelled": "🚫", "in_progress": "⚡",
               "running": "⚡", "pending": "⏳", "queued": "⏳", "waiting_plan": "📝",
               "waiting_question": "❓", "waiting_blocked": "⛔"}

TEMPLATE = "navaia_mj_realestate_t1"
TEMPLATE_BODY = (
    "السلام عليكم ورحمة الله وبركاته،\n{{1}}، تحية طيبة،\n\n{{2}}\n\n"
    "وقد لمست مكاتب سبقتكم الأثر: أرباحها أعلى بنسبة 30% وتكاليفها أقل بنسبة 40%، ضمن نظام حماية البيانات والأنظمة العقارية.\n\n"
    "يسعدني أن أوضح لكم الأثر المتوقّع على {{3}} تحديداً، ما هو الوقت المناسب لكم؟ {{4}}، أو راسلوني هنا.\n\n{{5}}\nشاكراً لكم"
)
V2 = ("في العمل العقاري، قد يبرد المهتمّ خلال دقائق إن تأخّر الردّ عليه، وقد تبقى وحدةٌ شاغرة "
      "أطول مما ينبغي. نڤايا تعمل إلى جانبكم فتردّ على مهتمّيكم فور وصولهم وتتابع تحصيل الإيجارات، دون عبء إضافي على فريقكم.")
V4 = "https://cal.com/abdulmajeed-alwardi"
V5 = "عبدالمجيد الوردي"
# INVENTED demo rows — this file ships to a PUBLIC repo. Three REAL prospects with their REAL
# mobile numbers were hardcoded here until 2026-07-21 and reached the public fork. Never paste a
# real lead into this list: it is the legacy /send demo path (disconnected from the CRM pipeline
# and due for retirement), so nothing is gained by it holding live data, and fake numbers also
# mean a stray tap on the demo path cannot message a real person.
LEADS = {
    1: {"name": "شركة المثال العقارية", "to": "+966500000001",
        "v1": "القائمون على شركة المثال الكرام", "v3": "شركة المثال العقارية"},
    2: {"name": "مؤسسة النموذج العقارية", "to": "+966500000002",
        "v1": "القائمون على مؤسسة النموذج الكرام", "v3": "مؤسسة النموذج العقارية"},
    3: {"name": "مجموعة التجربة العقارية", "to": "+966500000003",
        "v1": "القائمون على مجموعة التجربة الكرام", "v3": "مجموعة التجربة العقارية"},
}


def _env(key: str) -> str:
    # OS env wins (cloud/container deploy injects secrets this way), then local .env files.
    v = os.environ.get(key)
    if v:
        return v.strip()
    for p in (BIZ_ENV, SDK_ENV):
        try:
            m = re.search(rf"^{re.escape(key)}=(.+)$", open(p, encoding="utf-8").read(), re.M)
            if m:
                return m.group(1).strip()
        except OSError:
            continue
    raise SystemExit(f"{key} not found in env or .env")


def render(lead: dict) -> str:
    return (TEMPLATE_BODY.replace("{{1}}", lead["v1"]).replace("{{2}}", V2)
            .replace("{{3}}", lead["v3"]).replace("{{4}}", V4).replace("{{5}}", V5))


# ── CRM (Twenty) ──────────────────────────────────────────────────────────────
_crm_headers = None


def _crm_h():
    global _crm_headers
    if _crm_headers is None:
        _crm_headers = {"Authorization": f"Bearer {_env('TWENTY_TOKEN')}", "Content-Type": "application/json"}
    return _crm_headers


def lookup_company(name: str) -> dict:
    """Live single-company CRM lookup at card-render time — no cache held in memory,
    always-fresh data. ilike (no wildcards) = case-insensitive exact name match."""
    q = ("query C($f:CompanyFilterInput){companies(filter:$f,first:5){"
         "edges{node{name sector domainName{primaryLinkUrl} createdBy{name}}}}}")
    try:
        r = httpx.post(f"{CRM_BASE}/graphql", headers=_crm_h(),
                       json={"query": q, "variables": {"f": {"name": {"ilike": name.strip()}}}},
                       timeout=20)
        for e in r.json().get("data", {}).get("companies", {}).get("edges", []):
            n = e["node"]
            if "mjeed" not in ((n.get("createdBy") or {}).get("name") or "").lower():
                continue
            return {"website": (n.get("domainName") or {}).get("primaryLinkUrl") or "",
                    "sector": n.get("sector") or ""}
    except Exception:
        pass
    return {}


def _mask_phone(p: str) -> str:
    """Mask a phone for Telegram (PDPL data-minimization): keep country + last 3 digits."""
    d = re.sub(r"\D", "", p)
    return f"+{d[:3]}•••••{d[-3:]}" if len(d) >= 8 else "•••"


def company_block(lead: dict) -> str:
    # PDPL data-minimization: only what's needed to VERIFY the right lead before approving.
    # Address dropped; phone masked. Full number still goes to the cloud/Baian send task, not here.
    info = lookup_company(lead["name"])
    website = info.get("website") or "— لا يوجد موقع مُسجّل —"
    sector = info.get("sector") or "—"
    gsearch = "https://www.google.com/search?q=" + urllib.parse.quote(lead["name"])
    return (f"🏢 {lead['name']}\n🏷️ {sector}\n🌐 {website}\n📞 {_mask_phone(lead['to'])}\n🔎 تحقّق: {gsearch}")


def mark_whatsapped(phone: str) -> bool:
    """Find the person by phone and set leadStatus=WhatsApped (best-effort)."""
    digits = re.sub(r"\D", "", phone)[-9:]
    q = ("query P($first:Int!,$after:String){people(first:$first,after:$after){"
         "edges{node{id phones{primaryPhoneNumber} createdBy{name}}}pageInfo{hasNextPage endCursor}}}")
    cursor = None
    try:
        while True:
            v = {"first": 100}
            if cursor:
                v["after"] = cursor
            r = httpx.post(f"{CRM_BASE}/graphql", headers=_crm_h(), json={"query": q, "variables": v}, timeout=40)
            d = r.json().get("data", {}).get("people", {})
            for e in d.get("edges", []):
                n = e["node"]
                if "mjeed" not in ((n.get("createdBy") or {}).get("name") or "").lower():
                    continue
                ph = (n.get("phones") or {}).get("primaryPhoneNumber") or ""
                if re.sub(r"\D", "", ph)[-9:] == digits and digits:
                    pr = httpx.patch(f"{CRM_BASE}/rest/people/{n['id']}", headers=_crm_h(),
                                     json={"leadStatus": "WhatsApped"}, timeout=30)
                    return pr.status_code < 300
            pi = d.get("pageInfo", {})
            if pi.get("hasNextPage"):
                cursor = pi.get("endCursor")
            else:
                break
    except Exception:
        return False
    return False


# ── Telegram ──────────────────────────────────────────────────────────────────
class TG:
    def __init__(self, token: str, chat_id: str):
        self.base = f"https://api.telegram.org/bot{token}"
        self.chat = str(chat_id)
        self.offset = None
        self.c = httpx.Client(timeout=40)

    def send(self, text: str, buttons: list | None = None) -> None:
        body = {"chat_id": self.chat, "text": text, "disable_web_page_preview": True}
        if buttons:
            body["reply_markup"] = {"inline_keyboard": buttons}
        self.c.post(f"{self.base}/sendMessage", json=body)

    def send_long(self, text: str, header: str = "") -> None:
        """Send arbitrarily long text across as many messages as needed — no truncation.

        Telegram caps a message near 4096 chars; the batch-copy digest of a whole outreach
        run is longer than that, and the operator asked to be copied on EVERY message, so a
        silent [:3500] cut defeats the point. Split on blank lines where possible so a single
        rendered message is never sliced mid-body.
        """
        text = (text or "").strip()
        if not text:
            return
        limit = 3800
        chunks, buf = [], ""
        for para in text.split("\n\n"):
            piece = (para + "\n\n")
            if len(buf) + len(piece) > limit and buf:
                chunks.append(buf.rstrip())
                buf = ""
            # a single paragraph longer than the limit gets hard-split
            while len(piece) > limit:
                chunks.append(piece[:limit])
                piece = piece[limit:]
            buf += piece
        if buf.strip():
            chunks.append(buf.rstrip())
        total = len(chunks)
        for i, ch in enumerate(chunks, 1):
            tag = f"{header} (part {i}/{total})\n" if (header and total > 1) else (header + "\n" if header else "")
            self.send(tag + ch)

    def answer(self, cq_id: str, text: str = "") -> None:
        self.c.post(f"{self.base}/answerCallbackQuery", json={"callback_query_id": cq_id, "text": text})

    def drain(self) -> None:
        r = self.c.get(f"{self.base}/getUpdates", params={"timeout": 0}).json()
        ups = r.get("result", [])
        if ups:
            self.offset = ups[-1]["update_id"] + 1

    def poll(self):
        # Short long-poll so the task watcher runs ~every 8s between updates.
        params = {"timeout": 8}
        if self.offset is not None:
            params["offset"] = self.offset
        try:
            r = self.c.get(f"{self.base}/getUpdates", params=params).json()
        except httpx.TimeoutException:
            return []
        ups = r.get("result", [])
        if ups:
            self.offset = ups[-1]["update_id"] + 1
        return ups


MAIN_MENU = [
    [{"text": "🚀 Fire pipeline", "callback_data": "menu:pipeline"},
     {"text": "📇 CRM leads", "callback_data": "menu:leads"}],
    [{"text": "📊 Status", "callback_data": "menu:status"}, {"text": "🗂 Tasks", "callback_data": "menu:tasks"}],
    [{"text": "⏳ Approvals", "callback_data": "menu:approvals"}, {"text": "📈 Daily report", "callback_data": "menu:report"}],
    [{"text": "🆕 New task", "callback_data": "menu:newtask"}, {"text": "👥 Ask an agent", "callback_data": "menu:ask"}],
    [{"text": "💬 Chat", "callback_data": "menu:chat"}, {"text": "📣 Approve outreach sends", "callback_data": "menu:send"}],
    [{"text": "🔀 Send mode", "callback_data": "menu:mode"}, {"text": "❓ Help", "callback_data": "menu:help"}],
]
HELP = (
    "🤖 NAVAIA workforce bot — how to use\n\n"
    "Control your cloud workforce from here: tap the menu buttons, or type commands.\n\n"
    "COMMANDS\n"
    "• /task <text> — assign Ahmed (orchestrator) a job or pipeline\n"
    "• /ask <agent> <question> — ask one agent (e.g. /ask Tariq how many leads do we have?)\n"
    "• /chat <agent> — open a NEW back-and-forth chat with an agent (/menu to exit)\n"
    "• /chats — resume an existing conversation\n"
    "• (plain text) — assigned to Ahmed as a task\n"
    "• /status — recent tasks (quick list)\n"
    "• /tasks — browse running/completed tasks and read their output\n"
    "• /approvals — every task waiting on you, with Approve/Reject buttons\n"
    "• /report — daily ops summary (Rashid)\n"
    "• /scrape <n> — run discovery for n leads: Maps → qualify → review pains → CRM "
    "(costs credit per lead, so the number must be typed)\n"
    "• /send — approve outreach WhatsApp sends\n"
    "• /leads — CRM pipeline health: lead counts by status and vertical\n"
    "• /lead <name|phone> — find a specific lead in the CRM\n"
    "• /copy — get the FULL rendered copy of a batch (what was sent), untruncated, here in Telegram\n"
    "• /mode — switch sends between 🧪 TEST (to your number) and 🔴 LIVE (real leads), no restart\n"
    "• /menu — buttons · /help — this guide · /stop — stop the bot\n\n"
    "APPROVALS (human-in-the-loop)\n"
    "When a task you assigned pauses — needs plan approval (📝), asks a question (❓), or hits a "
    "blocker (⛔) — it lands here. A plan shows ✅ Approve; a question shows ✍️ Answer — tap it, "
    "type your reply, and the agent resumes WITH your answer. A blocker shows 🔁 Re-run (a blocked "
    "task can't take an answer — fix the dependency, then re-run it fresh). ❌ Reject cancels the "
    "task. Nothing proceeds until you decide. Tap ⏳ Approvals anytime to see all pending ones.\n\n"
    "TASKS\n"
    "🗂 Tasks lists running or completed tasks; tap one to read its full output (and Approve/Reject if it's waiting).\n\n"
    "CHAT\n"
    "💬 Chat starts a new conversation with an agent, OR resumes an existing one — pick from the list. "
    "Each message gets a reply; /menu leaves chat.\n\n"
    "SENDS\n"
    "/send shows each lead with company info + a Google verify link and ✅/⏭️ buttons. Approving delivers "
    "the WhatsApp and marks the lead 'WhatsApped' in the CRM.\n\n"
    "NOTE: this local bot runs only while your machine is on."
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--to-me", action="store_true", help="Route send approvals to MY_PHONE (test).")
    args = ap.parse_args()

    tg = TG(_env("TELEGRAM_BOT_TOKEN"), _env("TELEGRAM_CHAT_ID"))
    cloud = NavaiaForgeClient(api_key=_env("BUSINESS_NF"), base_url=CLOUD_BASE)
    my_phone = _env("MY_PHONE")
    agents = {a.name: a.id for a in cloud.agents.list(workforce_id=CLOUD_WF)}
    id_to_agent = {v: k for k, v in agents.items()}
    # state.mode ∈ {None, "task", "ask", "chat"}
    # state.to_me is the LIVE/TEST send toggle: True = TEST (route sends to MY_PHONE),
    # False = LIVE (send to the real lead). --to-me only sets the STARTING value; it can
    # be flipped at runtime from Telegram (🔀 Mode button / /mode) with no restart.
    state = {"mode": None, "agent": None, "conv": None, "conv_agent": None, "seen": set(),
             "answer_tid": None, "to_me": args.to_me}
    # tracked task_id -> {"agent": name, "kind": task|ask|report|send, "last": status, "lead": n|None, "born": ts}
    tracked: dict[str, dict] = {}
    print(f"Bot online. agents={list(agents)} company_info=live-lookup", flush=True)

    def mode_line() -> str:
        return ("🧪 *TEST mode* — outreach sends go to YOUR number "
                f"({_mask_phone(my_phone)}), not the real leads."
                if state["to_me"] else
                "🔴 *LIVE mode* — approved outreach sends go to the REAL leads.")

    def mode_menu() -> None:
        # Offer only the OTHER mode as the action; LIVE is the consequential one so it confirms.
        if state["to_me"]:
            btns = [[{"text": "🔴 Switch to LIVE (real leads)", "callback_data": "mode:golive"}]]
        else:
            btns = [[{"text": "🧪 Switch to TEST (send to me)", "callback_data": "mode:test"}]]
        tg.send(f"{mode_line()}\n\nThis flips instantly — no restart needed.", buttons=btns)

    tg.drain()
    tg.send("🟢 *NAVAIA workforce bot online.*\n" + mode_line(), buttons=MAIN_MENU)

    # ── task assignment + non-blocking watcher ────────────────────────────────
    def start_task(agent_id, agent_name, text, kind="task", lead=None):
        if not agent_id:
            tg.send(f"⚠️ No agent named *{agent_name}* in this workforce. Try 👥 Ask an agent.")
            return
        title = (f"SEND WA ({lead['name']})" if kind == "send" else text[:100])
        meta = {"source": "telegram"}
        if kind == "send":
            meta.update({"channel": "whatsapp", "to": lead["to"]})
        try:
            t = cloud.tasks.create(CLOUD_WF, title, description=text, agent_id=agent_id,
                                   priority="standard", metadata=meta)
        except Exception as e:
            tg.send(f"⚠️ Couldn't assign to *{agent_name}*: {e}")
            return
        tracked[t.id] = {"agent": agent_name, "kind": kind, "last": str(t.status).lower(),
                         "lead": lead, "born": time.time()}
        tg.send(f"✅ Assigned to *{agent_name}* — working… (you'll get results/approvals here)")

    def pipeline_menu():
        tg.send("📣 *Fire outreach* — reads Mjeed's *Not Contacted* leads straight from the "
                "CRM, fills the approved Touch-1 templates, and stops at the approval gate "
                "HERE as an ✍️ Answer card. Leads live in the CRM only; the laptop file is no "
                "longer a source.",
                buttons=[
                    [{"text": "📣 Outreach Not-Contacted CRM leads (all verticals)",
                      "callback_data": "pipe:outreach"}],
                ])

    def fire_pipeline(kind="outreach"):
        """Build the CRM outreach task in a background thread (prep can take a moment and must
        not block Telegram polling). The CRM is the ONLY lead source — the laptop lead file is
        never read (operator decision 2026-07-20). No Snov: build_outreach_task only normalizes
        and reads the CRM."""
        def run():
            try:
                import submit_lead_batch as slb
                built = slb.build_outreach_task(slb.ALL_VERTICALS)
                if built is None:
                    tg.send("📣 No *Not Contacted* leads in the CRM — nothing to send.")
                    return
                title, desc = built
                t = cloud.tasks.create(CLOUD_WF, title, description=desc,
                                       agent_id=agents.get("Ahmed"), priority="high",
                                       metadata={"kind": "outreach_existing",
                                                 "approval_gate": "hitl_any_channel",
                                                 "source": "telegram"})
                tracked[t.id] = {"agent": "Ahmed", "kind": "outreach", "last": None,
                                 "lead": None, "born": time.time()}
                tg.send(f"🚀 Outreach task created (`{str(t.id)[:8]}…`) — Ahmed is on it. "
                        "The rendered messages will arrive here for your approval, and the full "
                        "batch copy when it completes.")
            except SystemExit as e:
                tg.send(f"⚠️ Pipeline: {e}")
            except Exception as e:
                tg.send(f"⚠️ Pipeline failed: {e}")
        threading.Thread(target=run, daemon=True).start()
        tg.send("⏳ Preparing (CRM normalize + template embed)… a moment.")

    def waiting_buttons(tid, status):
        # Backend contract (app/tasks/service.py approve_task): /approve REQUIRES a JSON body
        # (a bodyless approve 422s) and accepts ONLY waiting_plan / waiting_question. A
        # waiting_blocked task can't be approved or answered (400 "not in a waiting state") —
        # it must be re-run once the blocking dependency is fixed.
        s = str(status).lower()
        if s == "waiting_blocked":
            return [[{"text": "🔁 Re-run", "callback_data": f"tretry:{tid}"},
                     {"text": "❌ Reject", "callback_data": f"treject:{tid}"}]]
        if s == "waiting_question":
            return [[{"text": "✍️ Answer", "callback_data": f"tanswer:{tid}"},
                     {"text": "❌ Reject", "callback_data": f"treject:{tid}"}]]
        return [[{"text": "✅ Approve", "callback_data": f"tapprove:{tid}"},
                 {"text": "✍️ Answer", "callback_data": f"tanswer:{tid}"},
                 {"text": "❌ Reject", "callback_data": f"treject:{tid}"}]]

    def approval_card(name, task, meta):
        s = str(task.status).lower()
        body = (task.result or "").replace("[DONE]", "").strip()
        tid = task.id
        if s == "waiting_plan":
            head = f"📝 *{name}* needs plan approval:"
        elif s == "waiting_question":
            head = f"❓ *{name}* asks (tap ✍️ Answer to reply):"
        else:
            head = f"⛔ *{name}* is blocked:"
        tg.send(f"{head}\n{body[:3000] or '(no detail provided)'}",
                buttons=waiting_buttons(tid, s))

    def _post_approve(tid, response=None):
        # The backend /approve endpoint REQUIRES a JSON body — a bodyless approve 422s
        # ("body Field required"), which is why the SDK's cloud.tasks.approve(tid) fails.
        # Always POST a body. `response` is stored as metadata.approval_response and folded
        # into the agent's interview on resume.
        body = {"response": response} if response else {}
        cloud.tasks._http.post(f"/tasks/{tid}/approve", body)

    def answer_task(tid, text):
        # Deliver the operator's typed answer to a waiting_plan / waiting_question task.
        try:
            _post_approve(tid, text)
            if tid in tracked:
                tracked[tid]["last"] = "in_progress"
            tg.send("✍️ Answer sent — resuming.")
        except Exception as e:
            tg.send(f"⚠️ Couldn't send answer: {e}\n"
                    "(If the task is ⛔ blocked it can't take an answer — tap 🔁 Re-run instead.)")

    def report_result(name, task, meta):
        s = str(task.status).lower()
        res = (task.result or "").replace("[DONE]", "").strip()
        copy_btn = [[{"text": "📋 Full copy", "callback_data": f"copy:{task.id}"}]]
        if s == "done":
            if meta.get("kind") == "send" and meta.get("lead") and not state["to_me"]:
                crm = "  · CRM: WhatsApped ✅" if mark_whatsapped(meta["lead"]["to"]) else "  · CRM update failed"
                tg.send(f"✅ Sent — *{meta['lead']['name']}*{crm}\n{res[:800]}")
            elif meta.get("kind") == "outreach":
                # Zero-cost send-copy: deliver the WHOLE rendered batch to the operator here,
                # untruncated, instead of an extra Snov/WhatsApp send per lead.
                tg.send(f"✅ *Outreach batch complete* — full copy of what was rendered/sent below.")
                tg.send_long(res, header="📋 Batch copy")
            else:
                tg.send(f"💬 *{name}*:\n{res[:3500]}" if res else f"✅ *{name}* finished (no text).",
                        buttons=copy_btn if len(res) > 3500 else None)
        elif s == "failed":
            tg.send(f"❌ *{name}* failed.\n{res[:1500]}",
                    buttons=copy_btn if len(res) > 1500 else None)
        else:
            tg.send(f"🚫 *{name}* {s}.")

    def watch():
        now = time.time()
        for tid, meta in list(tracked.items()):
            try:
                t = cloud.tasks.get(tid)
            except Exception:
                continue
            s = str(t.status).lower()
            name = meta["agent"]
            if s == meta["last"]:
                # still running — age out very old in-progress tasks so we don't poll forever
                if s not in WAITING_STATES and now - meta["born"] > 1800:
                    tg.send(f"⏳ *{name}* still working after 30m — see 📊 Status. (stopped tracking)")
                    tracked.pop(tid, None)
                continue
            meta["last"] = s
            if s in WAITING_STATES:
                # sends already got human approval via the send button → auto-clear the internal plan
                if meta["kind"] == "send" and s == "waiting_plan":
                    try:
                        _post_approve(tid)
                        meta["last"] = "in_progress"
                    except Exception:
                        pass
                    continue
                approval_card(name, t, meta)
            elif s in DONE_STATES:
                report_result(name, t, meta)
                tracked.pop(tid, None)

    def pending_approvals():
        try:
            allt = cloud.tasks.list(CLOUD_WF)
        except Exception as e:
            tg.send(f"approvals error: {e}"); return
        waiting = [t for t in allt if str(t.status).lower() in WAITING_STATES]
        if not waiting:
            tg.send("✅ Nothing waiting on you right now."); return
        tg.send(f"⏳ *{len(waiting)} task(s) waiting on you:*")
        for t in waiting[:10]:
            name = id_to_agent.get(t.agent_id, "agent")
            approval_card(name, t, {"kind": "task"})
            tracked.setdefault(t.id, {"agent": name, "kind": "task",
                                      "last": str(t.status).lower(), "lead": None, "born": time.time()})

    # ── chat (conversations API) ──────────────────────────────────────────────
    def open_chat(agent_name):
        # Create lazily on the first message so the conversation is titled with it
        # (SDK has no rename) — makes the resume list readable instead of all "Telegram chat".
        label = "the team (Ahmed routes)" if agent_name == "__team" else f"*{agent_name}*"
        state.update({"mode": "chat", "conv": None, "conv_agent": agent_name, "seen": set()})
        tg.send(f"💬 New chat with {label}. Send your first message; /menu to exit.")

    def chat_send(text):
        try:
            if not state["conv"]:
                who = "team" if state["conv_agent"] == "__team" else state["conv_agent"]
                aid = None if state["conv_agent"] == "__team" else agents.get(state["conv_agent"])
                conv = cloud.conversations.create(CLOUD_WF, title=f"{who}: {text[:40]}", agent_id=aid)
                state["conv"] = conv.id
            cloud.conversations.send_message(state["conv"], text)
        except Exception as e:
            tg.send(f"⚠️ Chat send failed: {e}"); return
        conv = state["conv"]
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                msgs = cloud.conversations.messages(conv)
            except Exception:
                msgs = []
            new = [m for m in msgs if getattr(m, "role", "") == "assistant" and m.id not in state["seen"]]
            for m in msgs:
                state["seen"].add(m.id)
            if new:
                who = state["conv_agent"] if state["conv_agent"] != "__team" else "team"
                tg.send(f"💬 *{who}*:\n{(new[-1].content or '').strip()[:3500]}")
                return
            time.sleep(3)
        tg.send("⏳ No reply yet — the agent may still be working. Keep chatting or /menu to exit.")

    def status():
        try:
            tasks = cloud.tasks.list(CLOUD_WF)[:10]
        except Exception as e:
            tg.send(f"status error: {e}"); return
        if not tasks:
            tg.send("No recent tasks."); return
        lines = ["*Recent tasks:*"]
        for t in tasks:
            lines.append(f"{STATUS_ICON.get(str(t.status).lower(),'🔄')} {str(t.title)[:48]}")
        tg.send("\n".join(lines))

    # ── CRM lead visibility (dashboard + search) — cloud-safe, reads the CRM ──
    _ACTIVE_VERTS = ["Real Estate", "Contracting & Facilities", "Training Institutes"]
    _STATUS_ORDER = ["Not Contacted", "Emailed", "Whatsapped", "Replied",
                     "Meeting Booked", "Closed", "Not Qualified", "Unresponsive"]

    def crm_leads():
        """Live pipeline health from the CRM: Mjeed's leads by status x vertical.

        This is what lets the operator run the business from the phone — the bot fires
        outreach but was otherwise blind to the actual lead inventory. Reads through the
        PAGINATED helper so the ~900-person CRM is never silently truncated.
        """
        try:
            import collections
            import pipeline_prep as prep
            ppl = prep.crm_people_fields("id leadStatus sector")
        except Exception as e:
            tg.send(f"CRM read error: {e}")
            return
        if not ppl:
            tg.send("No leads in the CRM under Mjeed yet.")
            return
        grid = collections.defaultdict(collections.Counter)
        totals = collections.Counter()
        for p in ppl:
            st = (p.get("leadStatus") or "—").strip().title()   # unify 'not contacted' casing
            sec = (p.get("sector") or "—").strip()
            grid[sec][st] += 1
            totals[st] += 1
        order = [s for s in _STATUS_ORDER if s in totals] + \
                [s for s in totals if s not in _STATUS_ORDER]
        lines = [f"📇 *CRM leads* — {len(ppl)} under Mjeed", ""]
        for sec in _ACTIVE_VERTS:
            c = grid.get(sec)
            if not c:
                continue
            parts = " · ".join(f"{s} {c[s]}" for s in order if c[s])
            lines.append(f"*{sec}* ({sum(c.values())})\n  {parts}")
        others = {s: grid[s] for s in grid if s not in _ACTIVE_VERTS}
        if others:
            oc = sum(sum(c.values()) for c in others.values())
            lines.append(f"\n_other / unsectored: {oc}_  "
                         f"({', '.join(sorted(others))[:70]})")
        lines.append("\n*Totals:* " + " · ".join(f"{s} {totals[s]}" for s in order))
        tg.send("\n".join(lines))

    def lead_search(q):
        """Find a specific lead by name or phone — look up a record from the phone."""
        import re
        q = (q or "").strip()
        if len(q) < 2:
            tg.send("Search needs at least 2 characters:  /lead <name or phone>")
            return
        try:
            import pipeline_prep as prep
            ppl = prep.crm_people_fields(
                "id name{firstName lastName} leadStatus sector jobTitle "
                "phones{primaryPhoneNumber} emails{primaryEmail}")
        except Exception as e:
            tg.send(f"CRM read error: {e}")
            return
        ql, qd = q.lower(), re.sub(r"\D", "", q)
        hits = []
        for p in ppl:
            nm = ((p.get("name") or {}).get("firstName", "") + " " +
                  (p.get("name") or {}).get("lastName", "")).strip()
            ph = (p.get("phones") or {}).get("primaryPhoneNumber", "") or ""
            if ql in nm.lower() or (len(qd) >= 4 and qd in re.sub(r"\D", "", ph)):
                hits.append((nm, p, ph))
        if not hits:
            tg.send(f"No CRM lead matches “{q}”.")
            return
        lines = [f"🔎 {len(hits)} match(es) for “{q}”:", ""]
        for nm, p, ph in hits[:12]:
            em = (p.get("emails") or {}).get("primaryEmail") or "-"
            role = p.get("jobTitle") or ""
            lines.append(f"• *{nm or '(no name)'}*{(' — ' + role) if role else ''}\n"
                         f"  {p.get('leadStatus') or '—'} · {p.get('sector') or '—'}\n"
                         f"  {ph or '-'} · {em}")
        if len(hits) > 12:
            lines.append(f"\n…and {len(hits) - 12} more — narrow the search.")
        tg.send("\n".join(lines))

    # ── task browser (view running / completed outputs) ───────────────────────
    def list_tasks(filt="all"):
        try:
            allt = cloud.tasks.list(CLOUD_WF)
        except Exception as e:
            tg.send(f"tasks error: {e}"); return
        if filt == "running":
            sel = [t for t in allt if str(t.status).lower() not in DONE_STATES]
        elif filt == "done":
            sel = [t for t in allt if str(t.status).lower() in DONE_STATES]
        else:
            sel = list(allt)
        sel = sel[:12]
        if not sel:
            tg.send(f"No {filt} tasks."); return
        rows = [[{"text": f"{STATUS_ICON.get(str(t.status).lower(),'🔄')} {str(t.title)[:40]}",
                  "callback_data": f"taskview:{t.id}"}] for t in sel]
        tg.send(f"🗂 *{filt}* tasks — tap to read the output:", buttons=rows)

    def view_task(tid):
        try:
            t = cloud.tasks.get(tid)
        except Exception as e:
            tg.send(f"couldn't fetch task: {e}"); return
        s = str(t.status).lower()
        tg.send(f"{STATUS_ICON.get(s,'🔄')} *{str(t.title)[:70]}*\nstatus: {s}")
        res = (t.result or "").replace("[DONE]", "").strip()
        if not res:
            tg.send("(no output yet)")
        else:
            preview = res[:3500]
            tg.send(preview, buttons=[[{"text": "📋 Full copy", "callback_data": f"copy:{tid}"}]]
                    if len(res) > 3500 else None)

    def full_copy(tid):
        """Post a task's ENTIRE result to Telegram, chunked — the persistent batch copy."""
        try:
            t = cloud.tasks.get(tid)
        except Exception as e:
            tg.send(f"couldn't fetch task: {e}"); return
        res = (t.result or "").replace("[DONE]", "").strip()
        if not res:
            tg.send("(no output to copy yet)"); return
        tg.send_long(res, header=f"📋 Copy — {str(t.title)[:50]}")
        if s in WAITING_STATES:
            hint = "This task asks a question — tap ✍️ Answer to reply:" if s == "waiting_question" \
                else "This task is waiting on you:"
            tg.send(hint, buttons=waiting_buttons(tid, s))

    # ── chat browser (resume an existing conversation) ────────────────────────
    def list_chats():
        try:
            convs = sorted(cloud.conversations.list(CLOUD_WF),
                           key=lambda c: getattr(c, "created_at", "") or "", reverse=True)[:6]
        except Exception as e:
            tg.send(f"⚠️ Couldn't list chats: {e}"); convs = []
        if not convs:
            tg.send("No past chats yet.", buttons=[[{"text": "🆕 New chat", "callback_data": "chatnew"}]]); return
        lines, btns, row = ["💬 *Resume a chat* — tap a number:", ""], [], []
        for i, c in enumerate(convs, 1):
            title = (getattr(c, "title", "") or "chat").strip()[:44] or "chat"
            when = (getattr(c, "created_at", "") or "")[:16].replace("T", " ")
            try:
                msgs = cloud.conversations.messages(c.id)
            except Exception:
                msgs = []
            if msgs:
                last = msgs[-1]
                who = "🧑" if getattr(last, "role", "") == "user" else "🤖"
                preview = f"{who} {(last.content or '').strip().replace(chr(10), ' ')[:90]}"
            else:
                preview = "— (empty)"
            lines.append(f"*{i}.* {title}  ·  {when}  ·  {len(msgs)} msgs\n    last: {preview}")
            row.append({"text": str(i), "callback_data": f"openconv:{c.id}"})
            if len(row) == 3:
                btns.append(row); row = []
        if row:
            btns.append(row)
        btns.append([{"text": "🆕 New chat", "callback_data": "chatnew"}])
        tg.send("\n".join(lines), buttons=btns)

    def open_existing_conv(conv_id):
        try:
            msgs = cloud.conversations.messages(conv_id)
        except Exception as e:
            tg.send(f"⚠️ Couldn't open chat: {e}"); return
        state.update({"mode": "chat", "conv": conv_id, "conv_agent": "chat",
                      "seen": {m.id for m in msgs}})
        if msgs:
            tail = "\n".join(f"{'🧑' if getattr(m,'role','')=='user' else '🤖'} "
                             f"{(m.content or '').strip()[:280]}" for m in msgs[-4:])
            tg.send(f"💬 Resumed ({len(msgs)} msgs). Recent:\n{tail}\n\nSend to continue; /menu to exit.")
        else:
            tg.send("💬 Resumed empty chat. Send to continue; /menu to exit.")

    def present_sends():
        tg.send(mode_line() + ("  ·  /mode to switch" if state["to_me"] else ""))
        for n, lead in LEADS.items():
            tg.send(f"📋 *Lead {n}* — approve WhatsApp Touch-1?\n\n{company_block(lead)}\n\n"
                    f"——— الرسالة ———\n{render(lead)}\n———",
                    buttons=[[{"text": f"✅ Approve {n}", "callback_data": f"approve:{n}"},
                              {"text": f"⏭️ Skip {n}", "callback_data": f"skip:{n}"}]])

    def do_send(n):
        lead = LEADS.get(n)
        if not lead:
            return
        to = my_phone if state["to_me"] else lead["to"]
        tg.send(f"🚀 Queuing send: lead {n} → {_mask_phone(to)} …")
        desc = (f"Send ONE WhatsApp via Baian to {to}. Use APPROVED template `{TEMPLATE}` (ar). "
                f"Fill body vars in order: {{{{1}}}}={lead['v1']} | {{{{2}}}}={V2} | {{{{3}}}}={lead['v3']} | "
                f"{{{{4}}}}={V4} | {{{{5}}}}={V5}. Introspect Baian tools; send_template to {to} ONLY. "
                "Do NOT look up CRM or message anyone else. Report template, message_id, delivered text, any error.")
        send_lead = dict(lead); send_lead["to"] = to
        start_task(TARIQ, id_to_agent.get(TARIQ, "Tariq"), desc, kind="send", lead=send_lead)

    # ── main loop ─────────────────────────────────────────────────────────────
    running = True
    while running:
        for u in tg.poll():
            cq = u.get("callback_query")
            msg = u.get("message")
            if cq:
                data = cq.get("data", "")
                tg.answer(cq["id"])
                if str((cq.get("message") or {}).get("chat", {}).get("id", "")) != tg.chat:
                    continue
                if data == "menu:status": status()
                elif data == "menu:pipeline": pipeline_menu()
                elif data == "menu:leads": crm_leads()
                elif data == "pipe:outreach": fire_pipeline("outreach")
                elif data == "menu:approvals": pending_approvals()
                elif data == "menu:tasks":
                    tg.send("🗂 Which tasks?", buttons=[[
                        {"text": "⚡ Running", "callback_data": "tasks:running"},
                        {"text": "✅ Completed", "callback_data": "tasks:done"},
                        {"text": "📋 All", "callback_data": "tasks:all"}]])
                elif data.startswith("taskview:"): view_task(data.split(":", 1)[1])
                elif data.startswith("copy:"): full_copy(data.split(":", 1)[1])
                elif data.startswith("tasks:"): list_tasks(data.split(":", 1)[1])
                elif data == "menu:report":
                    start_task(agents.get("Rashid"), "Rashid",
                               "Generate a 5-line summary of today's NAVAIA operations: wins, blockers, items needing attention.",
                               kind="report")
                elif data == "menu:newtask":
                    state["mode"] = "task"; tg.send("🆕 Send me the task description (goes to Ahmed).")
                elif data == "menu:ask":
                    tg.send("👥 Pick an agent:", buttons=[[{"text": nm, "callback_data": f"ask:{nm}"}] for nm in agents])
                elif data.startswith("ask:"):
                    state["mode"] = "ask"; state["agent"] = data[4:]
                    tg.send(f"✍️ Send your question for *{state['agent']}*.")
                elif data == "menu:chat": list_chats()
                elif data == "chatnew":
                    rows = [[{"text": nm, "callback_data": f"chat:{nm}"}] for nm in agents]
                    rows.append([{"text": "👥 The team (Ahmed routes)", "callback_data": "chat:__team"}])
                    tg.send("💬 New chat with whom?", buttons=rows)
                elif data.startswith("openconv:"): open_existing_conv(data.split(":", 1)[1])
                elif data.startswith("chat:"): open_chat(data[5:])
                elif data == "menu:send": present_sends()
                elif data.startswith("approve:"): do_send(int(data.split(":")[1]))
                elif data.startswith("skip:"): tg.send(f"⏭️ Lead {data.split(':')[1]} skipped.")
                elif data.startswith("tanswer:"):
                    state["mode"] = "answer"; state["answer_tid"] = data.split(":", 1)[1]
                    tg.send("✍️ Type your answer — I'll send it to the agent so it resumes with your reply.")
                elif data.startswith("tapprove:"):
                    tid = data.split(":", 1)[1]
                    try:
                        _post_approve(tid)
                        if tid in tracked: tracked[tid]["last"] = "in_progress"
                        tg.send("✅ Approved — resuming.")
                    except Exception as e:
                        tg.send(f"⚠️ Approve failed: {e}\n"
                                "(A ⛔ blocked task can't be approved — tap 🔁 Re-run.)")
                elif data.startswith("tretry:"):
                    tid = data.split(":", 1)[1]
                    try:
                        old = cloud.tasks.get(tid)
                        aid = getattr(old, "agent_id", None)
                        nm = id_to_agent.get(aid, "agent")
                        desc = (old.description or old.title or "")
                        cloud.tasks.reject(tid, "Superseded by re-run")
                        tracked.pop(tid, None)
                        nt = cloud.tasks.create(CLOUD_WF, f"[Re-run] {str(old.title)[:80]}",
                                                description=desc, agent_id=aid, priority="standard",
                                                metadata={"source": "telegram-retry"})
                        tracked[nt.id] = {"agent": nm, "kind": "task", "last": str(nt.status).lower(),
                                          "lead": None, "born": time.time()}
                        tg.send(f"🔁 Re-running as a fresh task for *{nm}*.")
                    except Exception as e:
                        tg.send(f"⚠️ Re-run failed: {e}")
                elif data.startswith("treject:"):
                    tid = data.split(":", 1)[1]
                    try:
                        cloud.tasks.reject(tid, "Rejected via Telegram")
                        tracked.pop(tid, None)
                        tg.send("❌ Rejected.")
                    except Exception as e:
                        tg.send(f"⚠️ Reject failed: {e}")
                elif data == "menu:mode": mode_menu()
                elif data == "mode:test":
                    state["to_me"] = True
                    tg.send("🧪 Switched to *TEST mode*.\n" + mode_line())
                elif data == "mode:golive":
                    # Extra confirm — LIVE means real WhatsApps go to real leads.
                    tg.send("⚠️ Go *LIVE*? Approved outreach sends will be delivered to the REAL leads.",
                            buttons=[[{"text": "🔴 Yes, go LIVE", "callback_data": "mode:live"},
                                      {"text": "↩️ Stay TEST", "callback_data": "mode:test"}]])
                elif data == "mode:live":
                    state["to_me"] = False
                    tg.send("🔴 Switched to *LIVE mode*.\n" + mode_line())
                elif data == "menu:help": tg.send(HELP)
                continue
            if not msg:
                continue
            if str(msg.get("chat", {}).get("id", "")) != tg.chat:
                continue
            text = (msg.get("text") or "").strip()
            if not text:
                continue
            low = text.lower()
            # commands always win, even inside a mode
            if low.startswith("/menu") or low.startswith("/start"):
                state["mode"] = None; tg.send("Main menu:", buttons=MAIN_MENU); continue
            if low.startswith("/stop"):
                tg.send("🔴 Bot stopping."); running = False; break
            if low.startswith("/help"): tg.send(HELP); continue
            if low.startswith("/status"): status(); continue
            if low.startswith("/tasks"): list_tasks("all"); continue
            if low.startswith("/approvals"): pending_approvals(); continue
            if low.startswith("/report"):
                start_task(agents.get("Rashid"), "Rashid", "Generate today's 5-line NAVAIA operations summary.", kind="report"); continue
            if low.startswith("/scrape"):
                # The batch size must be TYPED. There is no bare /scrape default on
                # purpose: this spends OpenRouter credit per lead (qualification + pain
                # extraction) and writes to the shared production CRM, so the number is the
                # operator's explicit instruction rather than something the bot assumes.
                arg = text[7:].strip()
                if not arg.isdigit() or not 1 <= int(arg) <= 50:
                    tg.send("🔎 *Scrape* — usage: `/scrape <n>` (1–50)\n\n"
                            "Runs discovery: Google Maps → qualify the vertical → read the "
                            "reviews for pains → enrich the site → write to the CRM.\n\n"
                            "Costs a little OpenRouter credit per lead and writes to the "
                            "shared CRM, so the batch size is not assumed — type it.\n"
                            "Example: `/scrape 10`")
                    continue
                n = int(arg)
                start_task(
                    agents.get("Rashid"), "Rashid",
                    f"Run discovery for {n} leads.\n\n"
                    f"Preflight scripts/discover.py first. If it is missing, STOP and "
                    f"report [WAITING:BLOCKED] — do not substitute another method and do "
                    f"not produce any leads.\n\n"
                    f"Then run:\n"
                    f"    python scripts/discover.py --source gmaps --limit {n}\n\n"
                    f"Report the counts the script actually printed (written / skipped / "
                    f"failed, pages fetched) and quote any WARN lines verbatim.",
                    kind="task")
                continue
            if low.startswith("/send"): present_sends(); continue
            if low.startswith("/leads"): crm_leads(); continue
            if low.startswith("/lead"):
                arg = text[5:].strip()
                lead_search(arg) if arg else crm_leads(); continue
            if low.startswith("/copy"):
                try:
                    recent = cloud.tasks.list(CLOUD_WF)[:8]
                except Exception as e:
                    tg.send(f"copy error: {e}"); continue
                if not recent:
                    tg.send("No tasks to copy."); continue
                rows = [[{"text": f"📋 {str(t.title)[:40]}", "callback_data": f"copy:{t.id}"}]
                        for t in recent]
                tg.send("Pick a batch to copy in full:", buttons=rows); continue
            if low.startswith("/mode"): mode_menu(); continue
            if low.startswith("/chats"): list_chats(); continue
            if low.startswith("/chat"):
                parts = text[5:].split(None, 1)
                open_chat(parts[0] if parts and parts[0] in agents else "__team"); continue
            if low.startswith("/task "):
                start_task(agents.get("Ahmed"), "Ahmed", text[6:].strip()); continue
            if low.startswith("/ask "):
                parts = text[5:].split(None, 1)
                if len(parts) == 2 and parts[0] in agents:
                    start_task(agents[parts[0]], parts[0], parts[1], kind="ask")
                else:
                    tg.send("Usage: /ask <AgentName> <question>. Agents: " + ", ".join(agents))
                continue
            # mode-driven input
            if state["mode"] == "answer":
                tid = state.get("answer_tid"); state["mode"] = None; state["answer_tid"] = None
                answer_task(tid, text); continue
            if state["mode"] == "chat": chat_send(text); continue
            if state["mode"] == "task":
                state["mode"] = None; start_task(agents.get("Ahmed"), "Ahmed", text); continue
            if state["mode"] == "ask":
                a = state["agent"]; state["mode"] = None
                start_task(agents.get(a), a, text, kind="ask"); continue
            # default: plain text → Ahmed
            start_task(agents.get("Ahmed"), "Ahmed", text)
        watch()
    print("Stopped.", flush=True)


if __name__ == "__main__":
    main()

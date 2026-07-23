"""Deploy the MJ-named option-B WhatsApp templates, then delete the previous vertical ones.

MJ naming (per user): navaia_mj_<vertical>_t1. Option B: {{2}} carries Lina's coupled
pain->solution block; the rest of the body is fixed and whole.

SAFETY: creates + verifies all 5 MJ templates FIRST. Only if every creation succeeds does it
delete the previous vertical templates — so we never delete the old set without a replacement.
Non-vertical templates (tests, surveys, meeting_confirmation, niqwa, welcome) are NOT touched.

Run in background; check approval later with: python scripts/check_baian_templates.py
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))
from navaia_forge import NavaiaForgeClient  # noqa: E402

import nav_env
CLOUD_BASE = nav_env.base_url()
CLOUD_WF = nav_env.CLOUD_WORKFORCE_ID
TARIQ = "6ba49326-4ec0-4b3b-8651-9526ec96894e"
ENV_PATH = os.path.join(REPO, ".env")
CAL = "https://cal.com/abdulmajeed-alwardi"
SIG = "عبدالمجيد الوردي"

VERTICALS = {
    "clinics": {"name": "navaia_mj_clinics_t1", "biz": "عيادات النخبة",
                "impact": "وقد لمست عياداتٌ سبقتكم الأثر: أرباحها أعلى بنسبة 30% وتكاليفها أقل بنسبة 40%، ضمن أنظمة وزارة الصحة وحماية البيانات."},
    "contracting": {"name": "navaia_mj_contracting_t1", "biz": "شركتكم",
                    "impact": "وقد لمست شركاتٌ سبقتكم الأثر: أرباحها أعلى بنسبة 30% وتكاليفها أقل بنسبة 40%، ضمن نظام حماية البيانات وأنظمة العمل."},
    "finance": {"name": "navaia_mj_finance_t1", "biz": "مكتبكم",
                "impact": "وقد لمست مكاتبُ سبقتكم الأثر: تحصيلها أعلى بنسبة 30% وتكاليفها أقل بنسبة 40%، ضمن أنظمة ساما ولوائح ممارسات التحصيل وحماية البيانات."},
    "realestate": {"name": "navaia_mj_realestate_t1", "biz": "مكتبكم",
                   "impact": "وقد لمست مكاتبُ سبقتكم الأثر: أرباحها أعلى بنسبة 30% وتكاليفها أقل بنسبة 40%، ضمن نظام حماية البيانات والأنظمة العقارية."},
    "training": {"name": "navaia_mj_training_t1", "biz": "معهدكم",
                 "impact": "وقد لمست معاهدُ سبقتكم الأثر: تسجيلاتها أعلى بنسبة 30% وتكاليفها أقل بنسبة 40%، ضمن نظام حماية البيانات وأنظمة التدريب."},
}

# previous VERTICAL outreach templates to remove (NOT the tests/surveys/other approved ones)
PREVIOUS = [
    "navaia_clinics_t1", "navaia_clinics_t1_v6", "navaia_clinics_t1_v7",
    "navaia_contracting_t1", "navaia_contracting_t1_v2",
    "navaia_finance_t1", "navaia_finance_t1_v2",
    "navaia_realestate_t1", "navaia_realestate_t1_v2",
    "navaia_training_t1", "navaia_training_t1_v2",
]


def _env(key: str) -> str:
    m = re.search(rf"^{re.escape(key)}=(.+)$", open(ENV_PATH, encoding="utf-8").read(), re.M)
    if not m:
        raise SystemExit(f"{key} not found")
    return m.group(1).strip()


def body_for(v: str) -> str:
    return ("السلام عليكم ورحمة الله وبركاته،\n{{1}}، تحية طيبة،\n\n{{2}}\n\n"
            f"{VERTICALS[v]['impact']}\n\n"
            "يسعدني أن أوضح لكم الأثر المتوقّع على {{3}} تحديداً، ما هو الوقت المناسب لكم؟ {{4}}، أو راسلوني هنا.\n\n{{5}}")


def _run(cloud, title, desc, meta, timeout=200):
    t = cloud.tasks.create(CLOUD_WF, title, description=desc, agent_id=TARIQ,
                           priority="standard", metadata=meta)
    print(f"  TASK {t.id} | {t.status}", flush=True)
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        t = cloud.tasks.get(t.id)
        if t.status != last:
            print(f"    -> {t.status}", flush=True); last = t.status
        s = str(t.status).lower()
        if "waiting_plan" in s:
            try: cloud.tasks.approve(t.id)
            except Exception: pass
        elif s in ("done", "failed", "cancelled", "waiting_blocked", "waiting_question"):
            break
        time.sleep(6)
    t = cloud.tasks.get(t.id)
    return t


def main() -> None:
    cloud = NavaiaForgeClient(api_key=_env("BUSINESS_NF"), base_url=CLOUD_BASE)

    print("=== PHASE 1: create MJ option-B templates ===", flush=True)
    created_ok = True
    for v, m in VERTICALS.items():
        name = m["name"]
        body = body_for(v)
        payload = json.dumps({
            "name": name,
            "category": "MARKETING",
            "language": "ar",
            "components": [{
                "type": "BODY",
                "text": body
            }]
        }, ensure_ascii=False)
        desc = f"""CRITICAL — READ THIS CAREFULLY BEFORE DOING ANYTHING.

Your ONLY job is to make ONE HTTP POST request and report the response. Nothing else.

Do NOT use Baian's create_template tool.
Do NOT check if the template already exists.
Do NOT modify, restructure, or "fix" the JSON below.
Do NOT retry with a different format if it fails.
Do NOT add, remove, or rename any JSON fields.
Do NOT send any message. Do NOT look up CRM.

Steps:
1. Read WABA_ID from env var NF_BAIAN_WABA_ID.
2. Read token from env var NF_BAIAN_META_TOKEN.
3. Make exactly ONE HTTP POST request:

POST https://graph.facebook.com/v24.0/{{{{WABA_ID}}}}/message_templates
Authorization: Bearer {{{{WHATSAPP_TOKEN}}}}
Content-Type: application/json

Body (send EXACTLY this, character for character, without ANY changes):
{payload}

4. Report the HTTP status code and the full response body verbatim.
5. STOP. Do nothing else."""
        print(f"[create {name}]", flush=True)
        t = _run(cloud, f"SUBMIT MJ (direct API): {name}", desc,
                 {"channel": "whatsapp", "template": name, "action": "create"})
        res = (t.result or "")
        ok = str(t.status).lower() == "done" and "error" not in res.lower()[:400] and "fail" not in res.lower()[:200]
        created_ok = created_ok and ok
        print(f"  FINAL {t.status} | ok={ok}: {res[:300]}\n", flush=True)

    if not created_ok:
        print("!! Not all MJ templates created cleanly — SKIPPING deletion of previous ones "
              "(safety). Review, fix, re-run.", flush=True)
        return

    print("=== PHASE 2: delete previous vertical templates ===", flush=True)
    for name in PREVIOUS:
        desc = f"""Delete a WhatsApp template by calling Meta's Graph API DIRECTLY.

Do NOT use Baian's delete_template tool. Call the Graph API directly via HTTP.

DELETE https://graph.facebook.com/v24.0/{{{{WABA_ID}}}}/message_templates?name={name}
Authorization: Bearer {{{{WHATSAPP_TOKEN}}}}

Use the WABA_ID and WHATSAPP_TOKEN from Baian's configured environment (env vars NF_BAIAN_WABA_ID and NF_BAIAN_META_TOKEN).
If the template does not exist, that is fine — just report it.
Report the HTTP status code and response body verbatim.
Do NOT delete any other template."""
        print(f"[delete {name}]", flush=True)
        t = _run(cloud, f"DELETE template: {name}", desc,
                 {"channel": "whatsapp", "template": name, "action": "delete"}, timeout=150)
        print(f"  FINAL {t.status}: {(t.result or '')[:200]}\n", flush=True)

    print("=== done. verify with check_baian_templates.py ===", flush=True)


if __name__ == "__main__":
    main()

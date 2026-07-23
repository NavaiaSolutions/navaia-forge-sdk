"""Prune the WhatsApp template set — delete everything except the approved MJ option-B set.

Baian is cloud-only, so every Graph API call runs as a cloud task assigned to Tariq
(the proven direct-Graph-API pattern from deploy_mj_templates.py). Secrets: BUSINESS_NF
from .env for auth; WABA id + Meta token come from Baian's cloud env
(NF_BAIAN_WABA_ID / NF_BAIAN_META_TOKEN) — never touched locally.

Modes:

    python scripts/manage_wa_templates.py cleanup
        Delete everything except the approved MJ set + keepers: superseded originals,
        MJ artifacts, test junk, and the old navaia_finance_t1 / navaia_training_t1.

    python scripts/manage_wa_templates.py recreate
        Create finance+training _v2 templates (option-B body).

    python scripts/manage_wa_templates.py inspect --ids <id1,id2,...>
        GET approved template bodies verbatim (for verification before sending).

    python scripts/manage_wa_templates.py finalize
        Delete old navaia_finance_t1 + navaia_training_t1 (standalone, if not using cleanup).

Verify anytime with: python scripts/check_baian_templates.py
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from navaia_forge import NavaiaForgeClient  # noqa: E402

import nav_env
CLOUD_BASE = nav_env.base_url()
CLOUD_WF = nav_env.CLOUD_WORKFORCE_ID
TARIQ = "6ba49326-4ec0-4b3b-8651-9526ec96894e"
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")
GRAPH = "https://graph.facebook.com/v24.0"

# --- rejected MJ finance/training: delete (by name) ---
REJECTED_TO_RECREATE = ["navaia_mj_finance_t1", "navaia_mj_training_t1"]

# --- superseded vertical originals (NOT finance/training — those are gated) ---
SUPERSEDED_ORIGINALS = [
    "navaia_clinics_t1",
    "navaia_clinics_t1_v6",
    "navaia_contracting_t1",
    "navaia_realestate_t1",
]

# --- stray MJ experiment artifacts (user-approved sweep) ---
MJ_ARTIFACTS = [
    "navaia_mj_clinics_t1_v2",
    "navaia_mj_clinics_t1_v3",
    "navaiamjclinicst1",
    "mjclinicst001",
    "navaia_mj_contracting_t1_20260710_144937",
    "navaia_diag_test_2",
    "test",
    "navaia_connectivity_test_v1",
    "test2",
]

# --- gated deletes (finalize only, after MJ replacements APPROVED) ---
GATED_ORIGINALS = ["navaia_finance_t1", "navaia_training_t1"]

# --- option-B bodies REPLICATING the APPROVED navaia_mj_realestate_t1 structure ---
# (bare {{2}} block; FIXED closing "شاكراً لكم" AFTER {{5}} so the body never ends on a
#  variable — the rule that rejected the originals with 2388299; keyed by vertical keyword)
_IMPACT = {
    "finance": "وقد لمست مكاتبُ سبقتكم الأثر: تحصيلها أعلى بنسبة 30% وتكاليفها أقل بنسبة 40%، ضمن أنظمة ساما ولوائح ممارسات التحصيل وحماية البيانات.",
    "training": "وقد لمست معاهدُ سبقتكم الأثر: تسجيلاتها أعلى بنسبة 30% وتكاليفها أقل بنسبة 40%، ضمن نظام حماية البيانات وأنظمة التدريب.",
    # contracting _v2: replaces navaia_mj_contracting_t1, whose Meta-locked closing has the
    # brand typo "فريق نفايا" (missing the ڤ). Same impact line as the approved t1 body.
    "contracting": "وقد لمست شركاتٌ سبقتكم الأثر: أرباحها أعلى بنسبة 30% وتكاليفها أقل بنسبة 40%، ضمن نظام حماية البيانات وأنظمة العمل.",
}

# Meta requires a sample for every variable: [{{1}} name, {{2}} coupled block, {{3}} business, {{4}} link, {{5}} signature]
CAL = "https://cal.com/abdulmajeed-alwardi"
SIG = "عبدالمجيد الوردي"
_EXAMPLE = {
    "finance": ["الأستاذ سعيد", "بين متابعة الأقساط المتأخّرة وتذكير العملاء، قد يتقادم بعض الديون، ونحن إلى جانب فريقكم نُؤتمت متابعة التحصيل في وقتها", "مكتبكم", CAL, SIG],
    "training": ["الأستاذ سعيد", "في موسم التسجيل قد يضيع بعض المستفسرين لتأخّر الردّ، ونحن إلى جانب فريقكم نُؤتمت الردّ على مستفسريكم ومتابعتهم", "معهدكم", CAL, SIG],
    "contracting": ["الأستاذ سعيد", "في أوقات الذروة قد يتأخّر الردّ على العروض والعطاءات فتفوتكم فرص، ونحن إلى جانب فريقكم نُؤتمت متابعة العروض والعطاءات في وقتها", "شركتكم", CAL, SIG],
}


def _env(key: str) -> str:
    m = re.search(rf"^{re.escape(key)}=(.+)$", open(ENV_PATH, encoding="utf-8").read(), re.M)
    if not m:
        raise SystemExit(f"{key} not found in {ENV_PATH}")
    return m.group(1).strip()


def _body(name: str) -> str:
    vert = next((v for v in _IMPACT if v in name), None)
    if vert is None:
        raise SystemExit(f"can't infer vertical (finance/training/contracting) from name: {name}")
    return (
        "السلام عليكم ورحمة الله وبركاته،\n{{1}}، تحية طيبة،\n\n{{2}}\n\n"
        f"{_IMPACT[vert]}\n\n"
        "يسعدني أن أوضح لكم الأثر المتوقّع على {{3}} تحديداً، ما هو الوقت المناسب لكم؟ {{4}}، أو راسلوني هنا.\n\n{{5}}\nشاكراً لكم"
    )


def _run(cloud, title, desc, meta, timeout=200):
    t = cloud.tasks.create(CLOUD_WF, title, description=desc, agent_id=TARIQ,
                           priority="standard", metadata=meta)
    print(f"  TASK {t.id} | {t.status}", flush=True)
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        t = cloud.tasks.get(t.id)
        if t.status != last:
            print(f"    -> {t.status}", flush=True)
            last = t.status
        s = str(t.status).lower()
        if "waiting_plan" in s:
            try:
                cloud.tasks.approve(t.id)
            except Exception:
                pass
        elif s in ("done", "failed", "cancelled", "waiting_blocked", "waiting_question"):
            break
        time.sleep(6)
    return cloud.tasks.get(t.id)


def _delete_batch(cloud, names, label):
    numbered = "\n".join(f"{i+1}. {n}" for i, n in enumerate(names))
    desc = f"""Delete several WhatsApp templates by calling Meta's Graph API DIRECTLY.

Do NOT use Baian's delete_template tool. Call the Graph API directly.
Read WABA_ID from env NF_BAIAN_WABA_ID and the token from env NF_BAIAN_META_TOKEN.

For EACH name in this list, make ONE HTTP request:
DELETE {GRAPH}/{{{{WABA_ID}}}}/message_templates?name=<NAME>
Authorization: Bearer {{{{WHATSAPP_TOKEN}}}}

Names to delete (delete every one; if a name does not exist, that is fine — just note it):
{numbered}

Do NOT delete any template not on this list. After each request, report:
<name> -> HTTP <status> <short response>. Give the full per-name result table. Do nothing else."""
    print(f"[delete-batch {label}: {len(names)} names]", flush=True)
    t = _run(cloud, f"DELETE templates batch: {label}", desc,
             {"channel": "whatsapp", "action": "delete_batch", "label": label}, timeout=260)
    print(f"  FINAL {t.status}:\n{(t.result or '')[:900]}\n", flush=True)
    return t


def _create(cloud, name):
    vert = next(v for v in _IMPACT if v in name)
    payload = json.dumps({
        "name": name,
        "category": "MARKETING",
        "language": "ar",
        "components": [{
            "type": "BODY",
            "text": _body(name),
            "example": {"body_text": [_EXAMPLE[vert]]},
        }],
    }, ensure_ascii=False)
    desc = f"""CRITICAL — READ CAREFULLY. Your ONLY job is ONE HTTP POST and report the response.

Do NOT use Baian's create_template tool. Do NOT modify, restructure, or "fix" the JSON.
Do NOT add/remove/rename fields. Do NOT retry with a different format. Do NOT send any message.

Steps:
1. Read WABA_ID from env NF_BAIAN_WABA_ID.
2. Read token from env NF_BAIAN_META_TOKEN.
3. Make exactly ONE HTTP POST:

POST {GRAPH}/{{{{WABA_ID}}}}/message_templates
Authorization: Bearer {{{{WHATSAPP_TOKEN}}}}
Content-Type: application/json

Body (send EXACTLY this, character for character):
{payload}

4. Report the HTTP status code and full response body verbatim. STOP."""
    print(f"[create {name}]", flush=True)
    t = _run(cloud, f"SUBMIT MJ (direct API): {name}", desc,
             {"channel": "whatsapp", "template": name, "action": "create"}, timeout=200)
    res = t.result or ""
    ok = str(t.status).lower() == "done" and "error" not in res.lower()[:400]
    print(f"  FINAL {t.status} | ok={ok}: {res[:300]}\n", flush=True)
    return ok




def inspect(cloud, ids):
    """GET the exact stored components (approved body verbatim) for given template ids."""
    idlist = "\n".join(f"- {i}" for i in ids)
    desc = f"""Read the EXACT stored definition of some approved WhatsApp templates via Meta's Graph API DIRECTLY.

Do NOT use Baian's tools. Read WABA_ID from env NF_BAIAN_WABA_ID and token from env NF_BAIAN_META_TOKEN.

For EACH template id below, make ONE HTTP GET:
GET {GRAPH}/<TEMPLATE_ID>?fields=name,language,category,status,components
Authorization: Bearer {{{{WHATSAPP_TOKEN}}}}

Template ids:
{idlist}

Report, for each id, the FULL JSON response VERBATIM — especially the complete `components`
array with the exact BODY `text` (every character, including any trailing text after the last
variable). Do not summarize or truncate the body text. Do nothing else."""
    print(f"[inspect {len(ids)} ids]", flush=True)
    t = _run(cloud, "INSPECT: approved MJ template bodies", desc,
             {"channel": "whatsapp", "action": "inspect"}, timeout=200)
    print(f"FINAL {t.status}:\n{t.result or ''}", flush=True)
    return t


def recreate(cloud, names=None, attempts=1, interval_min=15):
    """Create finance+training MJ templates under the given names (option-B body).

    Defaults to the fresh _v2 names (the _t1 names are under Meta's 30-day post-delete
    lock). Only CREATES — deletes/sweeps nothing, touches no approved template.
    With attempts>1 it waits interval_min between tries for any transient failure."""
    pending = list(names or ["navaia_mj_finance_t1_v2", "navaia_mj_training_t1_v2"])
    print(f"=== RECREATE: {pending} (attempts={attempts}, interval={interval_min}m) ===", flush=True)
    for i in range(1, attempts + 1):
        print(f"\n--- attempt {i}/{attempts} ---", flush=True)
        still = []
        for name in pending:
            if not _create(cloud, name):
                still.append(name)
        pending = still
        if not pending:
            print("\n=== RECREATE DONE — both created; awaiting Meta approval ===", flush=True)
            print("  verify: python scripts/check_baian_templates.py", flush=True)
            return
        if i < attempts:
            print(f"  still locked/failed: {pending} — waiting {interval_min}m…", flush=True)
            time.sleep(interval_min * 60)
    print(f"\n=== RECREATE INCOMPLETE — still failing: {pending} ===", flush=True)
    print("  Meta name-lock (2388023) persists. Re-run later, or switch to fresh names.", flush=True)


def finalize(cloud):
    print("=== FINALIZE: delete old finance+training originals (replacements must be APPROVED) ===", flush=True)
    _delete_batch(cloud, GATED_ORIGINALS, "gated-finance-training-originals")
    print("\n=== FINALIZE DONE — verify with check_baian_templates.py ===", flush=True)


def cleanup(cloud):
    """Delete everything except the approved MJ set: superseded originals, old _t1s,
    gated originals, plus all test/experiment artifacts."""
    print("=== PHASE 1: delete REJECTED mj finance+training (old _t1 names) ===", flush=True)
    _delete_batch(cloud, REJECTED_TO_RECREATE, "rejected-finance-training")

    print("=== PHASE 2: delete superseded originals + MJ artifacts + tests ===", flush=True)
    _delete_batch(cloud, SUPERSEDED_ORIGINALS + MJ_ARTIFACTS, "superseded+artifacts+tests")

    print("=== PHASE 3: delete gated originals (old finance+training) ===", flush=True)
    _delete_batch(cloud, GATED_ORIGINALS, "gated-finance-training-originals")

    print("\n=== CLEANUP DONE — verify with check_baian_templates.py ===", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["cleanup", "recreate", "finalize", "inspect"])
    ap.add_argument("--attempts", type=int, default=1, help="recreate: number of tries (waits between).")
    ap.add_argument("--interval-min", type=int, default=15, help="recreate: minutes between tries.")
    ap.add_argument("--names", default=None, help="recreate: comma-separated template names (default: the _v2 pair).")
    ap.add_argument("--ids", default=None, help="inspect: comma-separated template ids to GET.")
    args = ap.parse_args()
    cloud = NavaiaForgeClient(api_key=_env("BUSINESS_NF"), base_url=CLOUD_BASE)
    if args.mode == "recreate":
        names = [n.strip() for n in args.names.split(",")] if args.names else None
        recreate(cloud, names=names, attempts=args.attempts, interval_min=args.interval_min)
    elif args.mode == "inspect":
        ids = [i.strip() for i in (args.ids or "").split(",") if i.strip()]
        inspect(cloud, ids)
    else:
        {"cleanup": cleanup, "finalize": finalize}[args.mode](cloud)


if __name__ == "__main__":
    main()

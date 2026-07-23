# Playbook — Send WhatsApp via Baian (PROVEN)

> **SOP for a low-level executor.** Follow the numbered steps exactly. This flow was
> proven end-to-end on **2026-07-07** — two real WhatsApps delivered to the owner.

## Facts you must know first

- **Baian = WhatsApp/Meta integration. CLOUD-ONLY.** Its token lives only in the cloud
  integration config (`baian.navaia.sa`), redacted locally. There is **no local
  `BAIAN_TOKEN`**. Therefore a Baian send MUST run as a **task on the cloud workforce** —
  you cannot call Baian directly from a local script.
- The cloud workforce executes tasks **even while its `status` is `draft`** — no
  activation needed for a send. (Do NOT activate the workforce just to send.)
- **First-contact WhatsApp requires a Meta-APPROVED template** (`send_template`), not a
  free-form message. A brand-new template lands `PENDING` and Meta approval takes
  ~minutes. Use an **already-APPROVED** template to send immediately.
- A blocked task ends in `waiting_blocked` (terminal) and does **not** self-resume when a
  pending template later approves — you must re-run.

## Identity / constants

- Cloud base URL: `https://fareegi.navaia.sa`
- Cloud workforce id: `131bb52f-e5eb-44ad-8134-03dc6908b485`
- Sender agent = **Tariq** (SDR, owns sending): `6ba49326-4ec0-4b3b-8651-9526ec96894e`
- API key: read `BUSINESS_NF` from `.env`. Recipient default: `MY_PHONE` from `.env`.

## Steps

1. **(optional) Check template status** — read-only:
   ```bash
   .venv/Scripts/python.exe scripts/check_baian_templates.py
   ```
   Confirm the template you intend to use is `APPROVED`.
2. **Send** using the canonical script (creates the cloud task → approves the plan gate →
   polls → prints the Baian `message_id`):
   ```bash
   .venv/Scripts/python.exe scripts/baian_send.py --to +9665XXXXXXXX --template <approved_template_name>
   ```
   - Omit `--to` to default to `MY_PHONE`.
   - The script assigns the task to Tariq and dispatches a **self-contained task spec**
     (see `workforce/tasks/whatsapp_test_send.md`) telling the agent to introspect Baian's
     tools, use the approved template, and report the `message_id`.
3. **Confirm delivery** — the script prints `status: done` + `message_id`
   (`wamid.…`). Check the recipient's phone.

## If the send 404s on a phone-number id (seen 2026-07-14, worked around before)

Baian's send tool can carry a **stale phone-number id** (e.g. `938243176048092` → Graph API
404). Baian itself is reachable — the id is the problem, and it must never be trusted from
cache. The proven fallback (same pattern as template management) is a **direct Graph API
send from the task**:

1. Read `NF_BAIAN_WABA_ID` + `NF_BAIAN_META_TOKEN` from the cloud env.
2. **Discover** the current phone number id: `GET https://graph.facebook.com/v24.0/{WABA_ID}/phone_numbers`.
3. `POST …/{PHONE_NUMBER_ID}/messages` with the template payload
   (`messaging_product=whatsapp`, `type=template`, language `ar`, body parameters in order).

`baian_send.py`'s task spec and both pipeline task builders instruct this fallback
automatically — agents try Baian's tool first, then direct Graph.

## If you need NEW wording (not an existing template)

Create/prune via `scripts/manage_wa_templates.py` (**direct Graph API** — Baian's
create/delete tools were unreliable), then STOP — do not wait in-task (it hits
`waiting_blocked`). Two hard Meta rules (learned 2026-07-10 — both caused INVALID_FORMAT):

- **No leading/trailing `{{n}}`** (`error_subcode 2388299`): the body must **end on fixed
  text** after the last variable (approved pattern: `{{5}}` then `شاكراً لكم`) and include an
  `example.body_text` sample for every variable.
- **30-day name lock** (`error_subcode 2388023`): a **deleted** template's name+language
  can't be reused for ~30 days — recreate under a `_v2` name, not the deleted one.

1. Submit with `manage_wa_templates.py` (see `04_outreach_templates.md` for the approved
   realestate structure to replicate).
2. Poll `scripts/check_baian_templates.py` until `APPROVED` (minutes).
3. Re-run the send step above with the now-approved template name.
4. **Verify the approved body matches your copy verbatim** — on 2026-07-07 a submitted
   bilingual body came back approved as a shortened line. Meta can alter/approve a
   reduced body; always confirm before real outreach.

## Evidence (2026-07-07)

- `meeting_confirmation` (approved) → delivered, `message_id wamid.HBgMOTY2NTA4MzM0OTM0…`.
- Custom `navaia_connectivity_test_v1` (approved after ~minutes) → delivered,
  `message_id wamid.HBgMOTY2NTA4MzM0OTM0FQIAERgSQTA1QTVENjdCRDAzMjE3RDA3AA==`.

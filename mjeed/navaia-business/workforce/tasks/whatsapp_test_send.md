# Task spec — WhatsApp send via Baian

> A **self-contained task spec**: everything the cloud agent needs to execute is in the
> description below — this is the "container holds only tasks" model. Dispatch it with
> `scripts/baian_send.py` (which fills the placeholders and assigns it to Tariq).

**Assign to:** Tariq (`6ba49326-4ec0-4b3b-8651-9526ec96894e`) on cloud workforce
`131bb52f-e5eb-44ad-8134-03dc6908b485`.

**Title:** `SEND: WhatsApp via Baian ({{TEMPLATE}})`

**Description (dispatched verbatim, `{{...}}` filled in):**
```
Send ONE WhatsApp message via the Baian integration to {{TO}} (authorized recipient).

Use the ALREADY-APPROVED Meta template `{{TEMPLATE}}` — do NOT create or wait on any
template. Steps:
1. Introspect Baian's tools (do not hardcode endpoints). Inspect `{{TEMPLATE}}` for any
   required body/parameter variables.
2. Fill any required variables with a minimal sensible value; if none, send as-is.
3. Send via Baian's send_template tool to {{TO}}. Send to this number ONLY. Do NOT look
   up CRM leads, do NOT start a sequence, do NOT message anyone else.
Report: template used, variables filled, the Baian message_id, the exact final text
delivered, and any error. Do not fake success.
```

**Dispatch:**
```bash
.venv/Scripts/python.exe scripts/baian_send.py --to {{TO}} --template {{TEMPLATE}}
```

See `../playbooks/whatsapp_send_baian.md` for the full SOP and the new-template path.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nav_env
from navaia_forge import NavaiaForgeClient
from submit_lead_batch import resolve_agent, templates_block

cloud = NavaiaForgeClient(api_key=nav_env.env("BUSINESS_NF"), base_url=nav_env.base_url())

verticals = ["Real Estate", "Contracting & Facilities"]

# Embed the exact verbatim templates so Lina doesn't hallucinate signatures/numbers!
embedded_templates = templates_block(verticals)

title = "Outreach: Existing CRM leads (Real Estate + Contracting)"
desc = f"""## OBJECTIVE
We need to send Touch-1 outreach for our existing "Not Contacted" CRM leads in the "Real Estate" and "Contracting & Facilities" verticals.

Since these leads are already in the CRM, you may skip scraping. Please process them through our standard pipeline:
- Gather the leads from the CRM
- Write the Touch-1 personalized copy (using the verbatim templates below)
- Verify eligibility and score them (priority report)
- Gate for HITL approval
- Send via Snov and Baian

## CRITICAL TEMPLATE RULES FOR LINA:
- NO SIGNATURE in the email body! Snov.io auto-appends it.
- NO NUMBERS/LISTS in the email body! Keep it exactly as the template dictates.
- WHATSAPP MUST MATCH EXACTLY: Only fill the {{{{1}}}} to {{{{5}}}} variables. Do not change the closing or add anything else.

---
{embedded_templates}
---

Please start the chain!"""

task = cloud.tasks.create(
    workforce_id=nav_env.CLOUD_WORKFORCE_ID, 
    title=title, 
    description=desc,
    agent_id=resolve_agent(cloud, "Ahmed"), 
    priority="high"
)

print(f"Task successfully dispatched to the cloud!")
print(f"Task ID: {task.id}")

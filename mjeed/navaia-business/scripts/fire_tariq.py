import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nav_env
from navaia_forge import NavaiaForgeClient

cloud = NavaiaForgeClient(api_key=nav_env.env("BUSINESS_NF"), base_url=nav_env.base_url())

title = "Tariq: Execute Sends for Existing Leads"
desc = """## MANIFEST FROM LINA
**EXAMPLE MEP:**
- Contact ID: Use your tools to find in CRM
- Email: Use your tools to find in CRM
- WhatsApp Vars: `["حضرة المسؤول", "تأخّر متابعة العطاءات...", "EXAMPLE MEP", "https://cal.com/abdulmajeed-alwardi", "عبدالمجيد الوردي"]`

**شركة المثال للخدمات العقارية:**
- Contact ID: Use your tools to find in CRM
- Phone only (no email available)
- WhatsApp Vars: `["حضرة المسؤول", "Managing property listings...", "شركة المثال", "https://cal.com/abdulmajeed-alwardi", "عبدالمجيد الوردي"]`

## INSTRUCTION
This is the manifest. Please present it, output [WAITING:QUESTION] exactly once for HITL approval, and once approved, execute the Snov and Baian sends."""

agents = cloud.agents.list(workforce_id=nav_env.CLOUD_WORKFORCE_ID)
tariq_id = next(a.id for a in agents if a.name == "Tariq")

task = cloud.tasks.create(
    workforce_id=nav_env.CLOUD_WORKFORCE_ID, 
    title=title, 
    description=desc,
    agent_id=tariq_id, 
    priority="high"
)

print(f"Task successfully dispatched to Tariq!")
print(f"Task ID: {task.id}")

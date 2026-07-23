import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nav_env
from navaia_forge import NavaiaForgeClient

cloud = NavaiaForgeClient(api_key=nav_env.env("BUSINESS_NF"), base_url=nav_env.base_url())

title = "Outreach: End-to-End Scrape & Send (Finance)"
desc = """## OBJECTIVE
Find 2 Finance companies in Riyadh, write the Touch-1 personalized copy, and prepare to send."""

# Resolve Ahmed
agents = cloud.agents.list(workforce_id=nav_env.CLOUD_WORKFORCE_ID)
ahmed_id = next(a.id for a in agents if a.name == "Ahmed")

task = cloud.tasks.create(
    workforce_id=nav_env.CLOUD_WORKFORCE_ID, 
    title=title, 
    description=desc,
    agent_id=ahmed_id, 
    priority="high"
)

print(f"Task successfully dispatched to the cloud!")
print(f"Task ID: {task.id}")

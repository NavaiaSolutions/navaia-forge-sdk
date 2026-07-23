import os
import re
import glob

# File paths
root_dir = r"C:\Users\aabbo\navaia-business-workforce"
agents_dir = os.path.join(root_dir, "workforce", "agents")

# Old and new file names
rename_map = {
    "rashid_strategy.md": "rashid_scraper.md",
    "nora_finance.md": "nora_scorer.md",
    "tariq_sdr_lead_fetcher.md": "tariq_sdr_sender.md"
}

# 1. Update deploy_agents.py
deploy_py_path = os.path.join(root_dir, "scripts", "deploy_agents.py")
with open(deploy_py_path, "r", encoding="utf-8") as f:
    deploy_content = f.read()

deploy_content = deploy_content.replace('"tariq_sdr_lead_fetcher.md"', '"tariq_sdr_sender.md"')
deploy_content = deploy_content.replace('"nora_finance.md"', '"nora_scorer.md"')
deploy_content = deploy_content.replace('"rashid_strategy.md"', '"rashid_scraper.md"')

with open(deploy_py_path, "w", encoding="utf-8") as f:
    f.write(deploy_content)

# 2. Update README.md
readme_path = os.path.join(root_dir, "workforce", "README.md")
with open(readme_path, "r", encoding="utf-8") as f:
    readme_content = f.read()

readme_content = readme_content.replace('tariq_sdr_lead_fetcher.md', 'tariq_sdr_sender.md')
readme_content = readme_content.replace('nora_finance.md', 'nora_scorer.md')
readme_content = readme_content.replace('rashid_strategy.md', 'rashid_scraper.md')
readme_content = readme_content.replace('Finance', 'Eligibility & Scoring')
readme_content = readme_content.replace('Strategy', 'Scraper & Importer')

with open(readme_path, "w", encoding="utf-8") as f:
    f.write(readme_content)

# 3. Update 01_workforce_identity.md
id_path = os.path.join(root_dir, "workforce", "01_workforce_identity.md")
if os.path.exists(id_path):
    with open(id_path, "r", encoding="utf-8") as f:
        id_content = f.read()
    id_content = id_content.replace('tariq_sdr_lead_fetcher.md', 'tariq_sdr_sender.md')
    id_content = id_content.replace('nora_finance.md', 'nora_scorer.md')
    id_content = id_content.replace('rashid_strategy.md', 'rashid_scraper.md')
    with open(id_path, "w", encoding="utf-8") as f:
        f.write(id_content)

# 4. Rename the files
for old_name, new_name in rename_map.items():
    old_path = os.path.join(agents_dir, old_name)
    new_path = os.path.join(agents_dir, new_name)
    if os.path.exists(old_path):
        os.rename(old_path, new_path)

print("Files renamed and references updated successfully.")

# Telegram <-> cloud workforce bot — always-on deploy image.
#
# Build from the REPO ROOT (so the COPY paths resolve):
#   docker build -f deploy/telegram-bot/Dockerfile -t navaia-tg-bot .
#
# The bot is a thin client: it long-polls Telegram and drives the CLOUD
# workforce API. It only needs the NavaiaForge SDK (public PyPI) + httpx,
# and two source files. Secrets are injected as ENV VARS at run time
# (never baked into the image): see .env.example.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# navaia-forge pulls httpx/pydantic/websockets; pin the version we verified.
RUN pip install "navaia-forge==0.2.3" "httpx>=0.27"

# The bot + the pipeline toolkit it can fire from Telegram (🚀 menu):
# nav_env (config), pipeline_prep (normalize/enrich/templates), submit_lead_batch
# (batch + outreach task builders), lina_compose (pain->solution engine).
COPY scripts/nav_env.py scripts/telegram_workforce_bot.py scripts/pipeline_prep.py \
     scripts/submit_lead_batch.py scripts/lina_compose.py /app/scripts/
# Template source (parsed verbatim into tasks) + the scraped lead pool snapshot.
COPY workforce/04_outreach_templates.md /app/workforce/04_outreach_templates.md
COPY leads_scraped_compact.json /app/leads_scraped_compact.json
# Batch markers must survive rebuilds: seed /app/data from the baked snapshot once,
# then always use the volume copy (compose sets LEADS_FILE=/app/data/… + a volume).
RUN mkdir -p /app/data

# Starts in LIVE mode (send-approvals go to the real lead on tap; the human still
# approves each send). TEST vs LIVE is now a RUNTIME toggle — flip it from Telegram
# itself (🔀 Send mode button or /mode), no restart. Add --to-me below only to change
# the STARTING mode to TEST (routes send-approvals to MY_PHONE).
CMD ["sh", "-c", "cp -n /app/leads_scraped_compact.json /app/data/ 2>/dev/null; exec python scripts/telegram_workforce_bot.py"]

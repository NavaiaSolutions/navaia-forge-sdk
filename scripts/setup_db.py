"""Create all database tables for the NavaiaForge backend.

Run this once after starting the backend for the first time:

    docker cp scripts/setup_db.py navaia-forge-api:/tmp/
    docker exec -e PYTHONPATH=/app navaia-forge-api python /tmp/setup_db.py
"""

import sys
from pathlib import Path

app_dir = Path("/app")
if app_dir.is_dir() and str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

import asyncio

import app.auth.models  # noqa: F401
import app.auth.api_key_models  # noqa: F401
import app.hosting.models  # noqa: F401
import app.agents.models  # noqa: F401
import app.workforces.models  # noqa: F401
import app.tasks.models  # noqa: F401
import app.conversations.models  # noqa: F401
import app.knowledge.models  # noqa: F401
import app.integrations.models  # noqa: F401
import app.observability.models  # noqa: F401
import app.templates.models  # noqa: F401
import app.ratings.models  # noqa: F401
import app.sync.models  # noqa: F401
import app.sync.instance  # noqa: F401

from app.agents.models import Base
from app.deps import engine


async def setup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database ready")


if __name__ == "__main__":
    asyncio.run(setup())

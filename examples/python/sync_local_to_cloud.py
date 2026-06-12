"""
NavaiaForge SDK — Two-Way Sync Example

Build a workforce on your own local backend (where the compute runs on your
machine), then push it to the live Fareegi cloud so you can collaborate,
visualise it in the hosted UI, and list it on the marketplace. Later, pull
marketplace purchases back down to run them locally.

Identity is carried by a permanent ``origin_id`` on every entity, so a
workforce can make a full round-trip — push to cloud, edit in the cloud UI,
pull back — without ever duplicating.

Run:
    export NAVAIA_LOCAL_API_KEY=nf_local_...
    export NAVAIA_CLOUD_API_KEY=nf_cloud_...
    python examples/python/sync_local_to_cloud.py
"""

from __future__ import annotations

import os

from navaia_forge import NavaiaForgeClient, SyncConflictError

# ── Two clients: your local backend, and the live cloud ──────────────
local = NavaiaForgeClient(
    base_url=os.environ.get("NAVAIA_LOCAL_BASE_URL", "http://localhost:8001"),
    api_key=os.environ["NAVAIA_LOCAL_API_KEY"],
)
cloud = NavaiaForgeClient(
    base_url=os.environ.get("NAVAIA_CLOUD_BASE_URL", "https://fareegi.navaia.sa"),
    api_key=os.environ["NAVAIA_CLOUD_API_KEY"],
)

# ── 1. Build a small workforce locally ───────────────────────────────
wf = local.workforces.create(name="Research Team", description="Built locally")
researcher = local.agents.create(
    workforce_id=wf.id,
    name="Researcher",
    role="research",
    instructions="Find and summarize information on any topic.",
    model_provider="anthropic",
    model_name="sonnet",
)
writer = local.agents.create(
    workforce_id=wf.id,
    name="Writer",
    role="writer",
    instructions="Turn research notes into a polished brief.",
    model_provider="anthropic",
    model_name="sonnet",
)
local.workforces.edges.create(wf.id, researcher.id, writer.id, label="handoff")
print(f"Built local workforce {wf.id} with 2 agents + 1 edge")

# ── 2. Push it to the cloud ──────────────────────────────────────────
# push() exports from `local` and imports into `cloud` — the SDK makes
# both HTTP calls; the two backends never talk to each other.
try:
    result = local.sync.push(wf.id, remote=cloud)
except SyncConflictError as exc:
    # The cloud copy changed since the last sync. Either keep the remote
    # version (do nothing) or force-overwrite it with your local state.
    print("Conflict — remote was modified. Forcing local state to win.")
    print("  remote bundle instance:", exc.remote_bundle.instance_id if exc.remote_bundle else "?")
    result = local.sync.push(wf.id, remote=cloud, force=True)

print(f"Pushed to cloud: action={result.action}, cloud workforce={result.workforce_id}")
print(f"  agents: {result.agents}, edges: {result.edges}")

# ── 3. (Optional) Save a portable bundle to disk ─────────────────────
local.sync.export_to_file(wf.id, "research_team.json")
print("Wrote research_team.json (portable, secrets redacted)")

# ── 4. Pull a marketplace purchase back down to run locally ──────────
# After buying/forking a workforce in the cloud UI, pull it to your local
# backend. Re-pulling is safe: origin_id self-recognition updates in place
# instead of creating a duplicate.
cloud_workforce_id = result.workforce_id
pulled = local.sync.pull(cloud_workforce_id, remote=cloud)
print(f"Pulled back locally: action={pulled.action}, local workforce={pulled.workforce_id}")

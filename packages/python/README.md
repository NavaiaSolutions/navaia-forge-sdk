# NavaiaForge Python SDK

Official Python client for the [NavaiaForge](https://navaia.com) AI workforce platform.

This SDK is a complete, typed wrapper over the NavaiaForge HTTP + WebSocket API. Use it **standalone** to drive workforces from scripts, services, notebooks, or CI — or **alongside the NavaiaForge dashboard**, since both speak to the same backend and share the same workforces, agents, tasks, knowledge, and integrations.

## Installation

```bash
pip install navaia-forge
```

## Quickstart

```python
from navaia_forge import NavaiaForgeClient

client = NavaiaForgeClient(
    base_url="http://localhost:8000",
    api_key="nf_...",
)

workforces = client.workforces.list()
task = client.tasks.create(
    workforce_id=workforces[0].id,
    title="Review the PR",
)
final = client.tasks.wait_for_completion(task.id)
print(final.status, final.result)
```

All resource methods return typed [Pydantic v2](https://docs.pydantic.dev/) models. Errors raise `navaia_forge.NavaiaForgeError` (or a subclass: `NotFoundError`, `RateLimitError`, `ValidationError`, `AuthenticationError`, `PermissionError`, `ServerError`, `TimeoutError`).

## Real-time events

```python
from navaia_forge import NavaiaForgeWs, HttpConfig

ws = NavaiaForgeWs(HttpConfig(base_url="http://localhost:8000", api_key="nf_..."))
ws.on("task:status", lambda evt: print("task event:", evt))
ws.connect()
ws.run_forever()
```

Subscribable channels include `task:status`, `agent:status`, `chat:message`, and `system:*`.

## Resources

| Namespace | Methods |
|---|---|
| `client.workforces` | `list`, `get`, `get_full`, `create`, `update`, `delete`, edge CRUD, tool/knowledge linking |
| `client.agents` | `list`, `get`, `create`, `update`, `delete`, `list_featured`, `clone`, `export`, `list_workforce_members`, `attach_to_workforce`, `detach_from_workforce` |
| `client.tasks` | `list`, `get`, `create`, `approve`, `reject`, `retry`, `logs`, `wait_for_completion` |
| `client.conversations` | `list`, `create`, `messages`, `send_message` |
| `client.knowledge` | `list`, `get`, `create`, `upload_document`, `search`, `featured`, `download`, `delete` |
| `client.templates` | `list`, `get`, `create`, `instantiate`, `delete`, plus `client.templates.agents` for agent templates |
| `client.tools` | `list`, `get`, `featured`, `create`, `update`, `delete`, `attach_to_workforce`, `detach_from_workforce` |
| `client.integrations` | `list`, `list_plugins`, `get`, `create`, `update`, `delete` |
| `client.setup` | `options`, `validate`, `complete` |
| `client.observability` | `summary`, `cost`, `agent_metrics`, `agent_evaluations`, `log_token_usage` |
| `client.auth` | `me`, `register`, `login`, `refresh`, `create_key`, `validate`, `google_login_url`, `github_login_url` |

## Use it standalone or with the UI

- **Standalone:** the SDK is sufficient on its own — no dashboard required. Drive everything from Python: scripts, services, Airflow/Prefect tasks, Jupyter notebooks, custom CLIs, internal tools.
- **Alongside the dashboard:** anything you create programmatically (workforces, agents, tasks, knowledge bases, integrations) appears in the NavaiaForge UI immediately, and anything created in the UI is reachable from `client.*`. They are two views over one backend.

## Development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest --cov=navaia_forge
ruff check navaia_forge tests
```

## License

Apache-2.0

# NavaiaForge Python SDK

Official Python client for the [NavaiaForge](https://navaia.com) AI workforce platform.

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

# List workforces
workforces = client.workforces.list()

# Create a task and wait for it to finish
task = client.tasks.create(
    workforce_id=workforces[0].id,
    title="Review the PR",
)
final = client.tasks.wait_for_completion(task.id)
print(final.status, final.result)
```

All resource methods return typed [Pydantic v2](https://docs.pydantic.dev/) models, not raw `dict`s. Catch `navaia_forge.NavaiaForgeError` (or one of its subclasses such as `NotFoundError`, `RateLimitError`) for API errors.

## Real-time events

```python
from navaia_forge import NavaiaForgeWs, HttpConfig

ws = NavaiaForgeWs(HttpConfig(base_url="http://localhost:8000", api_key="nf_..."))
ws.on("task:status", lambda evt: print("task event:", evt))
ws.connect()
ws.run_forever()
```

## Resources

| Namespace | Methods |
|---|---|
| `client.workforces` | `list`, `get`, `get_full`, `create`, `update`, `delete` |
| `client.agents` | `list`, `get`, `create`, `update`, `delete` |
| `client.tasks` | `list`, `get`, `create`, `approve`, `reject`, `retry`, `wait_for_completion` |
| `client.conversations` | `list`, `create`, `messages`, `send_message` |
| `client.knowledge` | `list`, `create`, `upload_document`, `delete` |
| `client.observability` | `summary`, `token_usage` |
| `client.templates` | `list`, `get`, `instantiate` |
| `client.integrations` | `list`, `get`, `create`, `delete` |

## Development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

## License

Apache-2.0

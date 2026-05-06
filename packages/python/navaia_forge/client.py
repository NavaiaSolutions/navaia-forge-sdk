"""NavaiaForge Python SDK client.

The client is intentionally thin: it owns an :class:`HttpClient` instance and
exposes resource namespaces (``client.workforces``, ``client.agents``, ...).

Example::

    from navaia_forge import NavaiaForgeClient

    client = NavaiaForgeClient(
        base_url="http://localhost:8000",
        api_key="nf_...",
    )

    workforces = client.workforces.list()
    task = client.tasks.create(workforce_id=workforces[0].id, title="Review PR")
    completed = client.tasks.wait_for_completion(task.id)
"""

from __future__ import annotations

from typing import Any

import httpx

from .http import HttpClient, HttpConfig
from .resources import (
    AgentsResource,
    AuthResource,
    ConversationsResource,
    IntegrationsResource,
    KnowledgeResource,
    ObservabilityResource,
    SetupResource,
    TasksResource,
    TemplatesResource,
    ToolsResource,
    WorkforcesResource,
)


class NavaiaForgeClient:
    """Top-level entry point to the NavaiaForge SDK."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str = "",
        timeout: float = 60.0,
        *,
        http: HttpClient | None = None,
    ) -> None:
        self._config = HttpConfig(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
        )
        self._http = http if http is not None else HttpClient(self._config)

        # Resource namespaces.
        self.workforces = WorkforcesResource(self._http)
        self.agents = AgentsResource(self._http)
        self.tasks = TasksResource(self._http)
        self.conversations = ConversationsResource(self._http)
        self.knowledge = KnowledgeResource(self._http)
        self.observability = ObservabilityResource(self._http)
        self.templates = TemplatesResource(self._http)
        self.integrations = IntegrationsResource(self._http)
        self.tools = ToolsResource(self._http)
        self.setup = SetupResource(self._http)
        self.auth = AuthResource(self._http)

    # ── Configuration accessors ───────────────────────────────

    @property
    def base_url(self) -> str:
        return self._config.base_url

    @property
    def api_key(self) -> str:
        return self._config.api_key

    @property
    def timeout(self) -> float:
        return self._config.timeout

    @property
    def http(self) -> HttpClient:
        """Underlying HTTP transport (escape hatch for advanced calls)."""
        return self._http

    # ── Lifecycle ─────────────────────────────────────────────

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._http.close()

    def __enter__(self) -> NavaiaForgeClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ── Misc ──────────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        """Check API health (hits ``/health``, not ``/api/v1/health``)."""
        url = f"{self._config.base_url.rstrip('/')}/health"
        with httpx.Client(timeout=self._config.timeout) as client:
            response = client.get(url)
        response.raise_for_status()
        return response.json()

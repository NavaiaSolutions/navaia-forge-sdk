"""
NavaiaForge Python SDK — typed HTTP client.

Provides high-level access to all NavaiaForge API endpoints with
proper error handling, type hints, and Pythonic interface.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

import httpx


class NavaiaForgeError(Exception):
    """Raised when the NavaiaForge API returns an error."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"HTTP {status_code}: {message}")


@dataclass(frozen=True)
class _RequestConfig:
    base_url: str
    api_key: str
    timeout: float


def _make_request(
    config: _RequestConfig,
    method: str,
    path: str,
    *,
    json_body: Any | None = None,
    params: dict[str, str] | None = None,
    files: dict[str, Any] | None = None,
) -> Any:
    """Execute an HTTP request and return parsed JSON."""
    url = urljoin(config.base_url.rstrip("/") + "/", f"api/v1{path}")
    headers: dict[str, str] = {}

    if config.api_key:
        headers["X-API-Key"] = config.api_key

    with httpx.Client(timeout=config.timeout) as client:
        response = client.request(
            method,
            url,
            json=json_body,
            params=params,
            headers=headers,
            files=files,
        )

    if response.status_code == 204:
        return None

    if not response.is_success:
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text
        raise NavaiaForgeError(response.status_code, str(detail))

    return response.json()


# ── Resource Namespaces ──────────────────────────────────────


@dataclass(frozen=True)
class WorkforceResource:
    """CRUD operations for Workforces."""

    _config: _RequestConfig

    def list(self) -> list[dict[str, Any]]:
        return _make_request(self._config, "GET", "/workforces")

    def get(self, workforce_id: str) -> dict[str, Any]:
        return _make_request(self._config, "GET", f"/workforces/{workforce_id}")

    def get_full(self, workforce_id: str) -> dict[str, Any]:
        return _make_request(
            self._config, "GET", f"/workforces/{workforce_id}/full"
        )

    def create(
        self,
        name: str,
        *,
        description: str = "",
        runtime_mode: str = "claude_max",
        template_id: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "name": name,
            "description": description,
            "runtime_mode": runtime_mode,
        }
        if template_id:
            body["template_id"] = template_id
        return _make_request(self._config, "POST", "/workforces", json_body=body)

    def update(
        self, workforce_id: str, **kwargs: Any
    ) -> dict[str, Any]:
        return _make_request(
            self._config, "PATCH", f"/workforces/{workforce_id}", json_body=kwargs
        )

    def delete(self, workforce_id: str) -> None:
        _make_request(self._config, "DELETE", f"/workforces/{workforce_id}")


@dataclass(frozen=True)
class AgentResource:
    """CRUD operations for Agents."""

    _config: _RequestConfig

    def list(self, workforce_id: str | None = None) -> list[dict[str, Any]]:
        params = {}
        if workforce_id:
            params["workforce_id"] = workforce_id
        return _make_request(self._config, "GET", "/agents", params=params)

    def get(self, agent_id: str) -> dict[str, Any]:
        return _make_request(self._config, "GET", f"/agents/{agent_id}")

    def create(
        self,
        workforce_id: str,
        name: str,
        role: str,
        instructions: str,
        *,
        model_provider: str = "anthropic",
        model_name: str = "sonnet",
        max_turns: int = 25,
        tools: list[str] | None = None,
        knowledge_bases: list[str] | None = None,
        position_x: float = 0,
        position_y: float = 0,
    ) -> dict[str, Any]:
        body = {
            "workforce_id": workforce_id,
            "name": name,
            "role": role,
            "instructions": instructions,
            "model_provider": model_provider,
            "model_name": model_name,
            "max_turns": max_turns,
            "tools": tools or [],
            "knowledge_bases": knowledge_bases or [],
            "position_x": position_x,
            "position_y": position_y,
        }
        return _make_request(self._config, "POST", "/agents", json_body=body)

    def update(self, agent_id: str, **kwargs: Any) -> dict[str, Any]:
        return _make_request(
            self._config, "PATCH", f"/agents/{agent_id}", json_body=kwargs
        )

    def delete(self, agent_id: str) -> None:
        _make_request(self._config, "DELETE", f"/agents/{agent_id}")


@dataclass(frozen=True)
class TaskResource:
    """CRUD operations for Tasks."""

    _config: _RequestConfig

    def list(
        self, workforce_id: str, *, status: str | None = None
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if status:
            params["status"] = status
        return _make_request(
            self._config,
            "GET",
            f"/workforces/{workforce_id}/tasks",
            params=params,
        )

    def get(self, task_id: str) -> dict[str, Any]:
        return _make_request(self._config, "GET", f"/tasks/{task_id}")

    def create(
        self,
        workforce_id: str,
        title: str,
        *,
        description: str = "",
        agent_id: str | None = None,
        priority: str = "standard",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "workforce_id": workforce_id,
            "title": title,
            "description": description,
            "priority": priority,
        }
        if agent_id:
            body["agent_id"] = agent_id
        if metadata:
            body["metadata_json"] = metadata
        return _make_request(self._config, "POST", "/tasks", json_body=body)

    def approve(self, task_id: str) -> dict[str, Any]:
        return _make_request(self._config, "POST", f"/tasks/{task_id}/approve")

    def reject(self, task_id: str, reason: str = "") -> dict[str, Any]:
        return _make_request(
            self._config,
            "POST",
            f"/tasks/{task_id}/reject",
            json_body={"reason": reason},
        )

    def retry(self, task_id: str) -> dict[str, Any]:
        return _make_request(self._config, "POST", f"/tasks/{task_id}/retry")

    def wait_for_completion(
        self,
        task_id: str,
        *,
        poll_interval: float = 5.0,
        timeout: float = 300.0,
    ) -> dict[str, Any]:
        """Poll until task reaches a terminal state."""
        import time

        start = time.monotonic()
        while time.monotonic() - start < timeout:
            task = self.get(task_id)
            if task["status"] in ("done", "failed", "rejected"):
                return task
            time.sleep(poll_interval)
        raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")


@dataclass(frozen=True)
class ConversationResource:
    """Operations for Conversations and Messages."""

    _config: _RequestConfig

    def list(self, workforce_id: str) -> list[dict[str, Any]]:
        return _make_request(
            self._config, "GET", f"/workforces/{workforce_id}/conversations"
        )

    def create(
        self, workforce_id: str, title: str = ""
    ) -> dict[str, Any]:
        return _make_request(
            self._config,
            "POST",
            f"/workforces/{workforce_id}/conversations",
            json_body={"title": title},
        )

    def messages(self, conversation_id: str) -> list[dict[str, Any]]:
        return _make_request(
            self._config, "GET", f"/conversations/{conversation_id}/messages"
        )

    def send_message(
        self,
        conversation_id: str,
        content: str,
        *,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "conversation_id": conversation_id,
            "content": content,
        }
        if agent_id:
            body["agent_id"] = agent_id
        return _make_request(
            self._config,
            "POST",
            f"/conversations/{conversation_id}/messages",
            json_body=body,
        )


@dataclass(frozen=True)
class KnowledgeResource:
    """Operations for Knowledge Bases."""

    _config: _RequestConfig

    def list(self, workforce_id: str) -> list[dict[str, Any]]:
        return _make_request(
            self._config, "GET", f"/workforces/{workforce_id}/knowledge"
        )

    def create(
        self,
        workforce_id: str,
        name: str,
        *,
        description: str = "",
        source_type: str = "upload",
    ) -> dict[str, Any]:
        return _make_request(
            self._config,
            "POST",
            "/knowledge",
            json_body={
                "workforce_id": workforce_id,
                "name": name,
                "description": description,
                "source_type": source_type,
            },
        )

    def upload_document(
        self, knowledge_base_id: str, file_path: str
    ) -> dict[str, Any]:
        import os

        filename = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            return _make_request(
                self._config,
                "POST",
                f"/knowledge/{knowledge_base_id}/documents",
                files={"file": (filename, f)},
            )

    def delete(self, knowledge_base_id: str) -> None:
        _make_request(
            self._config, "DELETE", f"/knowledge/{knowledge_base_id}"
        )


@dataclass(frozen=True)
class ObservabilityResource:
    """Operations for metrics and observability."""

    _config: _RequestConfig

    def summary(self, workforce_id: str) -> dict[str, Any]:
        return _make_request(
            self._config, "GET", f"/workforces/{workforce_id}/metrics"
        )

    def token_usage(
        self, workforce_id: str, *, days: int = 7
    ) -> list[dict[str, Any]]:
        return _make_request(
            self._config,
            "GET",
            f"/workforces/{workforce_id}/metrics/tokens",
            params={"days": str(days)},
        )


@dataclass(frozen=True)
class TemplateResource:
    """Operations for Workforce Templates."""

    _config: _RequestConfig

    def list(self) -> list[dict[str, Any]]:
        return _make_request(self._config, "GET", "/templates")

    def get(self, template_id: str) -> dict[str, Any]:
        return _make_request(
            self._config, "GET", f"/templates/{template_id}"
        )

    def instantiate(
        self, template_id: str, name: str
    ) -> dict[str, Any]:
        return _make_request(
            self._config,
            "POST",
            f"/templates/{template_id}/instantiate",
            json_body={"name": name},
        )


# ── Main Client ──────────────────────────────────────────────


@dataclass(frozen=True)
class NavaiaForgeClient:
    """
    NavaiaForge Python SDK client.

    Usage:
        client = NavaiaForgeClient(
            base_url="http://localhost:8000",
            api_key="your-api-key",
        )

        # List workforces
        workforces = client.workforces.list()

        # Create a task
        task = client.tasks.create(
            workforce_id="...",
            title="Review the PR",
        )

        # Wait for completion
        result = client.tasks.wait_for_completion(task["id"])
    """

    base_url: str = "http://localhost:8000"
    api_key: str = ""
    timeout: float = 60.0

    @property
    def _config(self) -> _RequestConfig:
        return _RequestConfig(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
        )

    @property
    def workforces(self) -> WorkforceResource:
        return WorkforceResource(self._config)

    @property
    def agents(self) -> AgentResource:
        return AgentResource(self._config)

    @property
    def tasks(self) -> TaskResource:
        return TaskResource(self._config)

    @property
    def conversations(self) -> ConversationResource:
        return ConversationResource(self._config)

    @property
    def knowledge(self) -> KnowledgeResource:
        return KnowledgeResource(self._config)

    @property
    def observability(self) -> ObservabilityResource:
        return ObservabilityResource(self._config)

    @property
    def templates(self) -> TemplateResource:
        return TemplateResource(self._config)

    def health(self) -> dict[str, str]:
        """Check API health."""
        url = urljoin(self.base_url.rstrip("/") + "/", "health")
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url)
        response.raise_for_status()
        return response.json()

"""Template resources.

The backend exposes two distinct template families under ``/api/v1``:

* ``/workforce-templates`` — pre-baked multi-agent workforces with edges.
* ``/agent-templates``     — reusable single-agent blueprints.

Both are surfaced here. The top-level :class:`TemplatesResource` mirrors the
workforce-template endpoints (preserving the legacy ``client.templates.list()``
shape) and exposes a nested :attr:`agents` namespace for agent templates::

    client.templates.list()                  # workforce templates
    client.templates.agents.list()           # agent templates
    client.templates.instantiate("tpl_1", "My copy")
"""

from __future__ import annotations

from typing import Any

from ..http import HttpClient
from ..types import (
    AgentTemplate,
    AgentTemplateCreate,
    ModelProvider,
    TemplateInstantiateResult,
    WorkforceTemplate,
    WorkforceTemplateCreate,
)
from ._base import ResourceBase, parse_list, parse_model


def _drop_none(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip keys whose value is ``None`` so backend defaults apply."""
    return {key: value for key, value in payload.items() if value is not None}


class AgentTemplatesResource(ResourceBase):
    """Operations against ``/api/v1/agent-templates``."""

    def list(
        self,
        *,
        category: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[AgentTemplate]:
        """List agent templates, optionally filtered by ``category``."""
        params = _drop_none({"category": category, "offset": offset, "limit": limit})
        return parse_list(
            AgentTemplate,
            self._http.get_list("/agent-templates", params=params),
        )

    def get(self, template_id: str) -> AgentTemplate:
        """Fetch a single agent template by id."""
        return parse_model(
            AgentTemplate, self._http.get(f"/agent-templates/{template_id}")
        )

    def create(
        self,
        name: str,
        role: str,
        *,
        description: str = "",
        instructions: str = "",
        model_provider: ModelProvider = "anthropic",
        model_name: str = "sonnet",
        escalation_model: str | None = None,
        max_turns: int = 25,
        tools: list[dict[str, Any]] | None = None,
        config_json: dict[str, Any] | None = None,
        category: str = "general",
    ) -> AgentTemplate:
        """Create a new agent template."""
        payload = AgentTemplateCreate(
            name=name,
            role=role,
            description=description,
            instructions=instructions,
            model_provider=model_provider,
            model_name=model_name,
            escalation_model=escalation_model,
            max_turns=max_turns,
            tools=tools,
            config_json=config_json,
            category=category,
        ).model_dump(exclude_none=True)
        return parse_model(
            AgentTemplate, self._http.post("/agent-templates", payload)
        )

    def delete(self, template_id: str) -> None:
        """Delete an agent template (admin/owner)."""
        self._http.delete(f"/agent-templates/{template_id}")


class TemplatesResource(ResourceBase):
    """Operations against ``/api/v1/workforce-templates`` (and ``/agent-templates``)."""

    def __init__(self, http: HttpClient) -> None:
        super().__init__(http)
        self.agents = AgentTemplatesResource(http)

    # ── Workforce templates ──────────────────────────────────────

    def list(
        self,
        *,
        category: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[WorkforceTemplate]:
        """List available workforce templates."""
        params = _drop_none({"category": category, "offset": offset, "limit": limit})
        return parse_list(
            WorkforceTemplate,
            self._http.get_list("/workforce-templates", params=params),
        )

    def get(self, template_id: str) -> WorkforceTemplate:
        """Fetch a single workforce template by id."""
        return parse_model(
            WorkforceTemplate, self._http.get(f"/workforce-templates/{template_id}")
        )

    def create(
        self,
        name: str,
        *,
        description: str = "",
        runtime_mode: str = "claude_max",
        agents_config: list[dict[str, Any]] | None = None,
        edges_config: list[dict[str, Any]] | None = None,
        config_json: dict[str, Any] | None = None,
        category: str = "general",
        price_cents: int = 0,
        is_premium: bool = False,
        preview_json: dict[str, Any] | None = None,
    ) -> WorkforceTemplate:
        """Create a new workforce template."""
        payload = WorkforceTemplateCreate(
            name=name,
            description=description,
            runtime_mode=runtime_mode,
            agents_config=agents_config,
            edges_config=edges_config,
            config_json=config_json,
            category=category,
            price_cents=price_cents,
            is_premium=is_premium,
            preview_json=preview_json,
        ).model_dump(exclude_none=True)
        return parse_model(
            WorkforceTemplate, self._http.post("/workforce-templates", payload)
        )

    def instantiate(self, template_id: str, name: str) -> TemplateInstantiateResult:
        """Instantiate a workforce template into a new workforce.

        Returns a lightweight summary (``id``, ``name``, ``description``,
        ``agents_created``, ``edges_created``). Use ``client.workforces.get(id)``
        to fetch the full :class:`Workforce` afterwards.
        """
        return parse_model(
            TemplateInstantiateResult,
            self._http.post(
                f"/workforce-templates/{template_id}/instantiate",
                {"name": name},
            ),
        )

    def delete(self, template_id: str) -> None:
        """Delete a workforce template (admin/owner)."""
        self._http.delete(f"/workforce-templates/{template_id}")

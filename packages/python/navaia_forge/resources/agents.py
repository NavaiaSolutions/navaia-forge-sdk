"""Agent resource."""

from __future__ import annotations

from typing import Any

from ..types import Agent, ModelProvider
from ._base import ResourceBase, parse_list, parse_model


class AgentsResource(ResourceBase):
    """CRUD operations for agents."""

    def list(self, workforce_id: str | None = None) -> list[Agent]:
        """List agents, optionally scoped to a workforce."""
        params: dict[str, Any] = {}
        if workforce_id is not None:
            params["workforce_id"] = workforce_id
        return parse_list(Agent, self._http.get_list("/agents", params=params or None))

    def get(self, agent_id: str) -> Agent:
        """Fetch a single agent by id."""
        return parse_model(Agent, self._http.get(f"/agents/{agent_id}"))

    def create(
        self,
        workforce_id: str,
        name: str,
        role: str,
        instructions: str,
        *,
        model_provider: ModelProvider = "anthropic",
        model_name: str = "sonnet",
        max_turns: int = 25,
        tools: list[dict[str, Any]] | None = None,
        knowledge_bases: list[str] | None = None,
        position_x: float = 0,
        position_y: float = 0,
        config_json: dict[str, Any] | None = None,
    ) -> Agent:
        """Create an agent inside a workforce."""
        body: dict[str, Any] = {
            "workforce_id": workforce_id,
            "name": name,
            "role": role,
            "instructions": instructions,
            "model_provider": model_provider,
            "model_name": model_name,
            "max_turns": max_turns,
            "tools": list(tools) if tools is not None else [],
            "knowledge_bases": list(knowledge_bases) if knowledge_bases is not None else [],
            "position_x": position_x,
            "position_y": position_y,
        }
        if config_json is not None:
            body["config_json"] = config_json
        return parse_model(Agent, self._http.post("/agents", body))

    def update(self, agent_id: str, **fields: Any) -> Agent:
        """Patch the agent with the supplied fields."""
        return parse_model(Agent, self._http.patch(f"/agents/{agent_id}", fields))

    def delete(self, agent_id: str) -> None:
        """Delete an agent."""
        self._http.delete(f"/agents/{agent_id}")

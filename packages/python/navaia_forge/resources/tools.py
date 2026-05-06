"""Tools resource — library + workforce composition."""

from __future__ import annotations

from typing import Any

from ..types import Tool, WorkforceToolLink
from ._base import ResourceBase, parse_list, parse_model


class ToolsResource(ResourceBase):
    """CRUD on the tool library plus workforce attach/detach."""

    # ── Library CRUD ──────────────────────────────────────────

    def list(self) -> list[Tool]:
        """List every tool in the caller's library."""
        return parse_list(Tool, self._http.get_list("/tools"))

    def list_featured(self) -> list[Tool]:
        """List featured / template tools."""
        return parse_list(Tool, self._http.get_list("/tools/featured"))

    def get(self, tool_id: str) -> Tool:
        """Fetch a tool by id."""
        return parse_model(Tool, self._http.get(f"/tools/{tool_id}"))

    def create(
        self,
        name: str,
        kind: str,
        *,
        description: str = "",
        icon: str | None = None,
        integration_id: str | None = None,
        config_json: dict[str, Any] | None = None,
    ) -> Tool:
        """Register a new tool in the library."""
        body: dict[str, Any] = {
            "name": name,
            "description": description,
            "kind": kind,
        }
        if icon is not None:
            body["icon"] = icon
        if integration_id is not None:
            body["integration_id"] = integration_id
        if config_json is not None:
            body["config_json"] = config_json
        return parse_model(Tool, self._http.post("/tools", body))

    def update(self, tool_id: str, **fields: Any) -> Tool:
        """Update a tool (server uses PUT)."""
        return parse_model(Tool, self._http.put(f"/tools/{tool_id}", fields))

    def delete(self, tool_id: str) -> None:
        """Delete a tool from the library."""
        self._http.delete(f"/tools/{tool_id}")

    # ── Workforce composition ─────────────────────────────────

    def list_workforce_tools(self, workforce_id: str) -> list[WorkforceToolLink]:
        """List tools currently attached to a workforce (with overrides)."""
        payload = self._http.get(f"/workforces/{workforce_id}/tools")
        if not isinstance(payload, list):
            return []
        return [WorkforceToolLink.model_validate(item) for item in payload]

    def attach_to_workforce(
        self,
        workforce_id: str,
        tool_id: str,
        *,
        override_json: dict[str, Any] | None = None,
    ) -> WorkforceToolLink:
        """Attach a tool to a workforce, optionally with config overrides."""
        body: dict[str, Any] = {"tool_id": tool_id}
        if override_json is not None:
            body["override_json"] = override_json
        return parse_model(
            WorkforceToolLink,
            self._http.post(f"/workforces/{workforce_id}/tools", body),
        )

    def detach_from_workforce(self, workforce_id: str, tool_id: str) -> None:
        """Detach a tool from a workforce."""
        self._http.delete(f"/workforces/{workforce_id}/tools/{tool_id}")

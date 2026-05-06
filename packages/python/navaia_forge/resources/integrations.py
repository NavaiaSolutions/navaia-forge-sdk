"""Integrations resource — plugins, install/CRUD on integrations."""

from __future__ import annotations

from typing import Any

from ..types import AvailablePlugin, Integration
from ._base import ResourceBase, parse_list, parse_model


class IntegrationsResource(ResourceBase):
    """Operations for installable integration plugins (Slack, GitHub, etc.)."""

    # ── Plugin registry ──────────────────────────────────────────

    def list_plugins(self) -> list[AvailablePlugin]:
        """List all integration plugins registered on the server."""
        return parse_list(AvailablePlugin, self._http.get("/plugins"))

    # ── Integrations CRUD ────────────────────────────────────────

    def list(
        self,
        *,
        workforce_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Integration]:
        """List integrations, optionally scoped to a workforce."""
        params: dict[str, Any] = {"offset": offset, "limit": limit}
        if workforce_id is not None:
            params["workforce_id"] = workforce_id
        return parse_list(
            Integration, self._http.get_list("/integrations", params=params)
        )

    def get(self, integration_id: str) -> Integration:
        """Fetch a single integration by id (server-side fetch via list filter).

        The backend does not currently expose a single-integration GET endpoint;
        this helper round-trips through ``list()`` and filters client-side.
        """
        for item in self.list():
            if item.id == integration_id:
                return item
        # Match the backend's 404 contract by raising via the standard error path.
        raise LookupError(f"Integration {integration_id!r} not found")

    def create(
        self,
        workforce_id: str,
        plugin_name: str,
        *,
        display_name: str = "",
        config_json: dict[str, Any] | None = None,
    ) -> Integration:
        """Install and activate a plugin against a workforce."""
        body: dict[str, Any] = {
            "workforce_id": workforce_id,
            "plugin_name": plugin_name,
            "display_name": display_name,
            "config_json": config_json or {},
        }
        return parse_model(Integration, self._http.post("/integrations", body))

    def update(
        self,
        integration_id: str,
        *,
        display_name: str | None = None,
        config_json: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> Integration:
        """Update an integration's display name, config, or status."""
        body: dict[str, Any] = {}
        if display_name is not None:
            body["display_name"] = display_name
        if config_json is not None:
            body["config_json"] = config_json
        if status is not None:
            body["status"] = status
        return parse_model(
            Integration,
            self._http.put(f"/integrations/{integration_id}", body),
        )

    def delete(self, integration_id: str) -> None:
        """Uninstall an integration (deactivates the plugin)."""
        self._http.delete(f"/integrations/{integration_id}")

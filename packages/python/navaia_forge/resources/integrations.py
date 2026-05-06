"""Integrations resource."""

from __future__ import annotations

from typing import Any

from ..types import Integration
from ._base import ResourceBase, parse_list, parse_model


class IntegrationsResource(ResourceBase):
    """Operations for external integrations (Slack, GitHub, etc.)."""

    def list(self, workforce_id: str) -> list[Integration]:
        """List integrations for a workforce."""
        return parse_list(
            Integration,
            self._http.get_list(f"/workforces/{workforce_id}/integrations"),
        )

    def get(self, integration_id: str) -> Integration:
        """Fetch a single integration by id."""
        return parse_model(
            Integration, self._http.get(f"/integrations/{integration_id}")
        )

    def create(
        self,
        workforce_id: str,
        name: str,
        type: str,
        *,
        category: str = "",
        config_json: dict[str, Any] | None = None,
    ) -> Integration:
        """Connect a new integration."""
        body: dict[str, Any] = {
            "workforce_id": workforce_id,
            "name": name,
            "type": type,
            "category": category,
        }
        if config_json is not None:
            body["config_json"] = config_json
        return parse_model(Integration, self._http.post("/integrations", body))

    def delete(self, integration_id: str) -> None:
        """Disconnect / delete an integration."""
        self._http.delete(f"/integrations/{integration_id}")

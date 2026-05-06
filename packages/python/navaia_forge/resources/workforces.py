"""Workforce resource (CRUD)."""

from __future__ import annotations

from typing import Any

from ..types import RuntimeMode, Workforce, WorkforceFull
from ._base import ResourceBase, parse_list, parse_model


class WorkforcesResource(ResourceBase):
    """CRUD operations for workforces."""

    def list(self) -> list[Workforce]:
        """List all workforces visible to the caller."""
        return parse_list(Workforce, self._http.get_list("/workforces"))

    def get(self, workforce_id: str) -> Workforce:
        """Fetch a single workforce by id."""
        return parse_model(Workforce, self._http.get(f"/workforces/{workforce_id}"))

    def get_full(self, workforce_id: str) -> WorkforceFull:
        """Fetch a workforce with its agents and edges populated."""
        return parse_model(
            WorkforceFull, self._http.get(f"/workforces/{workforce_id}/full")
        )

    def create(
        self,
        name: str,
        *,
        description: str = "",
        runtime_mode: RuntimeMode = "claude_max",
        template_id: str | None = None,
        config_json: dict[str, Any] | None = None,
    ) -> Workforce:
        """Create a workforce."""
        body: dict[str, Any] = {
            "name": name,
            "description": description,
            "runtime_mode": runtime_mode,
        }
        if template_id is not None:
            body["template_id"] = template_id
        if config_json is not None:
            body["config_json"] = config_json
        return parse_model(Workforce, self._http.post("/workforces", body))

    def update(self, workforce_id: str, **fields: Any) -> Workforce:
        """Patch the workforce with the supplied fields (server uses PUT)."""
        return parse_model(
            Workforce,
            self._http.patch(f"/workforces/{workforce_id}", fields),
        )

    def delete(self, workforce_id: str) -> None:
        """Delete a workforce."""
        self._http.delete(f"/workforces/{workforce_id}")

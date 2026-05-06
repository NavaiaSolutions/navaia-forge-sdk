"""Workforce resource (CRUD) and the nested ``edges`` sub-resource."""

from __future__ import annotations

from typing import Any

from ..http import HttpClient
from ..types import ApprovalMode, Edge, RuntimeMode, Workforce, WorkforceFull
from ._base import ResourceBase, parse_list, parse_model


class EdgesResource(ResourceBase):
    """CRUD for workforce edges (graph topology between agents)."""

    def create(
        self,
        workforce_id: str,
        source_agent_id: str,
        target_agent_id: str,
        *,
        approval_mode: ApprovalMode = "auto_run",
        condition_expr: str | None = None,
        label: str = "",
        max_runs: int | None = None,
        task_mode: str = "sequential",
    ) -> Edge:
        """Create an edge between two agents in a workforce."""
        body: dict[str, Any] = {
            "workforce_id": workforce_id,
            "source_agent_id": source_agent_id,
            "target_agent_id": target_agent_id,
            "approval_mode": approval_mode,
            "label": label,
            "task_mode": task_mode,
        }
        if condition_expr is not None:
            body["condition_expr"] = condition_expr
        if max_runs is not None:
            body["max_runs"] = max_runs
        return parse_model(Edge, self._http.post("/edges", body))

    def update(self, edge_id: str, **fields: Any) -> Edge:
        """Patch an edge with the supplied fields (server uses PUT)."""
        return parse_model(Edge, self._http.put(f"/edges/{edge_id}", fields))

    def delete(self, edge_id: str) -> None:
        """Delete an edge."""
        self._http.delete(f"/edges/{edge_id}")

    def list(self, workforce_id: str) -> list[Edge]:
        """List edges for a workforce.

        The backend has no dedicated list endpoint; this convenience method
        fetches the workforce's ``/full`` view and returns ``edges``.
        """
        full = self._http.get(f"/workforces/{workforce_id}/full")
        if isinstance(full, dict):
            edges = full.get("edges", [])
            return parse_list(Edge, edges)
        return []


class WorkforcesResource(ResourceBase):
    """CRUD operations for workforces."""

    def __init__(self, http: HttpClient) -> None:
        super().__init__(http)
        self.edges = EdgesResource(http)

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
        """Update the workforce with the supplied fields (server uses PUT)."""
        return parse_model(
            Workforce,
            self._http.put(f"/workforces/{workforce_id}", fields),
        )

    def delete(self, workforce_id: str) -> None:
        """Delete a workforce."""
        self._http.delete(f"/workforces/{workforce_id}")

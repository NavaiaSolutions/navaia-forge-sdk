"""Knowledge base resource (KBs, documents, search, library)."""

from __future__ import annotations

from typing import Any

from ..types import (
    KnowledgeBase,
    KnowledgeSourceType,
    SearchResponse,
    SearchResult,
)
from ._base import ResourceBase, parse_list, parse_model


class KnowledgeResource(ResourceBase):
    """Operations for knowledge bases and search."""

    # ── KB CRUD ───────────────────────────────────────────────

    def list_all(self) -> list[KnowledgeBase]:
        """List every knowledge base in the caller's library."""
        return parse_list(KnowledgeBase, self._http.get_list("/knowledge-bases"))

    def list(self, workforce_id: str) -> list[KnowledgeBase]:
        """List the knowledge bases belonging to a workforce.

        The backend scopes KBs by ``workforce_id`` on the collection endpoint
        (``GET /knowledge-bases?workforce_id=...``); the param is required.
        """
        return parse_list(
            KnowledgeBase,
            self._http.get_list(
                "/knowledge-bases", params={"workforce_id": workforce_id}
            ),
        )

    def get(self, knowledge_base_id: str) -> KnowledgeBase:
        """Fetch a knowledge base by id."""
        return parse_model(
            KnowledgeBase,
            self._http.get(f"/knowledge-bases/{knowledge_base_id}"),
        )

    def create(
        self,
        name: str,
        *,
        description: str = "",
        workforce_id: str | None = None,
        source_type: KnowledgeSourceType = "upload",
        retrieval_mode: str = "semantic",
        config_json: dict[str, Any] | None = None,
    ) -> KnowledgeBase:
        """Create a knowledge base (library or workforce-scoped)."""
        body: dict[str, Any] = {
            "name": name,
            "description": description,
            "retrieval_mode": retrieval_mode,
            "source_type": source_type,
        }
        if workforce_id is not None:
            body["workforce_id"] = workforce_id
        if config_json is not None:
            body["config_json"] = config_json
        return parse_model(KnowledgeBase, self._http.post("/knowledge-bases", body))

    def update(self, knowledge_base_id: str, **fields: Any) -> KnowledgeBase:
        """Update a knowledge base (server uses PATCH)."""
        return parse_model(
            KnowledgeBase,
            self._http.patch(f"/knowledge-bases/{knowledge_base_id}", fields),
        )

    def delete(self, knowledge_base_id: str) -> None:
        """Delete a knowledge base."""
        self._http.delete(f"/knowledge-bases/{knowledge_base_id}")

    # ── Search ────────────────────────────────────────────────

    def search(
        self,
        knowledge_base_id: str,
        query: str,
        *,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Run a semantic / keyword search against a KB.

        Returns the result list directly (use :meth:`search_response` for
        the full envelope including ``query`` and ``total``).
        """
        return self.search_response(
            knowledge_base_id, query, top_k=top_k, filters=filters
        ).results

    def search_response(
        self,
        knowledge_base_id: str,
        query: str,
        *,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> SearchResponse:
        """Run a search and return the full :class:`SearchResponse` envelope."""
        body: dict[str, Any] = {"query": query, "top_k": top_k}
        if filters is not None:
            body["filters"] = filters
        return parse_model(
            SearchResponse,
            self._http.post(f"/knowledge-bases/{knowledge_base_id}/search", body),
        )

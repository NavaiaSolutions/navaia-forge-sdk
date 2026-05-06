"""Knowledge base resource (KBs, documents, search, library)."""

from __future__ import annotations

import os
from typing import Any

from ..types import (
    KnowledgeBase,
    KnowledgeDocument,
    KnowledgeSourceType,
    SearchResponse,
    SearchResult,
    WorkforceKnowledgeBaseLink,
)
from ._base import ResourceBase, parse_list, parse_model


class KnowledgeResource(ResourceBase):
    """Operations for knowledge bases, documents, attachments, and search."""

    # ── KB CRUD ───────────────────────────────────────────────

    def list_all(self) -> list[KnowledgeBase]:
        """List every knowledge base in the caller's library."""
        return parse_list(KnowledgeBase, self._http.get_list("/knowledge-bases"))

    def list_featured(self) -> list[KnowledgeBase]:
        """List featured / templated knowledge bases."""
        return parse_list(
            KnowledgeBase,
            self._http.get_list("/knowledge-bases/featured"),
        )

    def list(self, workforce_id: str) -> list[KnowledgeBase]:
        """List knowledge bases attached to a workforce.

        Returns the inner :class:`KnowledgeBase` from each attachment.
        """
        payload = self._http.get(f"/workforces/{workforce_id}/knowledge-bases")
        if not isinstance(payload, list):
            return []
        return [
            KnowledgeBase.model_validate(item["knowledge_base"])
            for item in payload
            if isinstance(item, dict) and "knowledge_base" in item
        ]

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
        """Update a knowledge base (server uses PUT)."""
        return parse_model(
            KnowledgeBase,
            self._http.put(f"/knowledge-bases/{knowledge_base_id}", fields),
        )

    def delete(self, knowledge_base_id: str) -> None:
        """Delete a knowledge base."""
        self._http.delete(f"/knowledge-bases/{knowledge_base_id}")

    # ── Workforce attachment ──────────────────────────────────

    def attach_to_workforce(
        self, workforce_id: str, knowledge_base_id: str
    ) -> WorkforceKnowledgeBaseLink:
        """Attach an existing KB to a workforce."""
        return parse_model(
            WorkforceKnowledgeBaseLink,
            self._http.post(
                f"/workforces/{workforce_id}/knowledge-bases",
                {"knowledge_base_id": knowledge_base_id},
            ),
        )

    def detach_from_workforce(
        self, workforce_id: str, knowledge_base_id: str
    ) -> None:
        """Detach a KB from a workforce."""
        self._http.delete(
            f"/workforces/{workforce_id}/knowledge-bases/{knowledge_base_id}"
        )

    # ── Documents ─────────────────────────────────────────────

    def upload_document(
        self, knowledge_base_id: str, file_path: str
    ) -> KnowledgeDocument:
        """Upload a document file to a knowledge base."""
        filename = os.path.basename(file_path)
        with open(file_path, "rb") as fh:
            payload = self._http.upload(
                f"/knowledge-bases/{knowledge_base_id}/documents",
                "file",
                (filename, fh),
            )
        return parse_model(KnowledgeDocument, payload)

    def download_document(self, knowledge_base_id: str, document_id: str) -> bytes:
        """Download the raw bytes for a document."""
        return self._http.download(
            f"/knowledge-bases/{knowledge_base_id}/documents/{document_id}/download"
        )

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

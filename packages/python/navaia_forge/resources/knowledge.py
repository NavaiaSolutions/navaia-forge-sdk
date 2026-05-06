"""Knowledge base resource."""

from __future__ import annotations

import os
from typing import Any

from ..types import KnowledgeBase, KnowledgeDocument, KnowledgeSourceType
from ._base import ResourceBase, parse_list, parse_model


class KnowledgeResource(ResourceBase):
    """Operations for knowledge bases and documents."""

    def list(self, workforce_id: str) -> list[KnowledgeBase]:
        """List knowledge bases for a workforce."""
        return parse_list(
            KnowledgeBase,
            self._http.get_list(f"/workforces/{workforce_id}/knowledge"),
        )

    def create(
        self,
        workforce_id: str,
        name: str,
        *,
        description: str = "",
        source_type: KnowledgeSourceType = "upload",
    ) -> KnowledgeBase:
        """Create a knowledge base."""
        body: dict[str, Any] = {
            "workforce_id": workforce_id,
            "name": name,
            "description": description,
            "source_type": source_type,
        }
        return parse_model(KnowledgeBase, self._http.post("/knowledge", body))

    def upload_document(
        self, knowledge_base_id: str, file_path: str
    ) -> KnowledgeDocument:
        """Upload a document to a knowledge base."""
        filename = os.path.basename(file_path)
        with open(file_path, "rb") as fh:
            payload = self._http.upload(
                f"/knowledge/{knowledge_base_id}/documents",
                "file",
                (filename, fh),
            )
        return parse_model(KnowledgeDocument, payload)

    def delete(self, knowledge_base_id: str) -> None:
        """Delete a knowledge base."""
        self._http.delete(f"/knowledge/{knowledge_base_id}")

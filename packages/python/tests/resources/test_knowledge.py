"""Smoke tests for KnowledgeResource."""

from __future__ import annotations

import pytest


@pytest.mark.integration
def test_list_knowledge_bases(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/knowledge",
        method="GET",
        json={
            "items": [
                {
                    "id": "kb_1",
                    "workforce_id": "wf_1",
                    "name": "Docs",
                    "source_type": "upload",
                }
            ],
            "total": 1,
        },
    )
    kbs = client.knowledge.list("wf_1")
    assert kbs[0].name == "Docs"


@pytest.mark.integration
def test_create_knowledge_base(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/knowledge",
        method="POST",
        json={
            "id": "kb_1",
            "workforce_id": "wf_1",
            "name": "Docs",
            "source_type": "upload",
        },
    )
    kb = client.knowledge.create("wf_1", "Docs")
    assert kb.id == "kb_1"

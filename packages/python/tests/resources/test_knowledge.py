"""Tests for KnowledgeResource."""

from __future__ import annotations

import pytest

from navaia_forge import KnowledgeBase, SearchResult


@pytest.fixture
def kb_payload() -> dict:
    return {
        "id": "kb_1",
        "workforce_id": "wf_1",
        "name": "Docs",
        "description": "All the docs",
        "source_type": "upload",
        "config_json": {},
        "document_count": 3,
    }


# ── KB CRUD ───────────────────────────────────────────────────


@pytest.mark.integration
def test_list_workforce_kbs(httpx_mock, client, base_url, kb_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/knowledge-bases?workforce_id=wf_1",
        method="GET",
        json={"items": [kb_payload], "total": 1},
    )
    kbs = client.knowledge.list("wf_1")
    assert kbs[0].id == "kb_1"


@pytest.mark.integration
def test_list_all(httpx_mock, client, base_url, kb_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/knowledge-bases",
        method="GET",
        json={"items": [kb_payload], "total": 1},
    )
    kbs = client.knowledge.list_all()
    assert isinstance(kbs[0], KnowledgeBase)


@pytest.mark.integration
def test_create_knowledge_base(httpx_mock, client, base_url, kb_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/knowledge-bases",
        method="POST",
        json=kb_payload,
    )
    kb = client.knowledge.create("Docs", workforce_id="wf_1")
    assert kb.id == "kb_1"


@pytest.mark.integration
def test_get_knowledge_base(httpx_mock, client, base_url, kb_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/knowledge-bases/kb_1",
        method="GET",
        json=kb_payload,
    )
    assert client.knowledge.get("kb_1").id == "kb_1"


@pytest.mark.integration
def test_update_knowledge_base_uses_patch(httpx_mock, client, base_url, kb_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/knowledge-bases/kb_1",
        method="PATCH",
        json={**kb_payload, "name": "Updated Docs"},
    )
    kb = client.knowledge.update("kb_1", name="Updated Docs")
    assert kb.name == "Updated Docs"


@pytest.mark.integration
def test_delete_knowledge_base(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/knowledge-bases/kb_1",
        method="DELETE",
        status_code=204,
    )
    assert client.knowledge.delete("kb_1") is None


# ── Search ───────────────────────────────────────────────────


@pytest.mark.integration
def test_search(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/knowledge-bases/kb_1/search?q=answer&max_results=3",
        method="POST",
        json={
            "results": [
                {
                    "content": "the answer is 42",
                    "score": 0.92,
                    "document_id": "doc_1",
                    "filename": "readme.md",
                    "chunk_index": 0,
                    "metadata": {},
                }
            ],
            "query": "answer",
            "total": 1,
        },
    )
    results = client.knowledge.search("kb_1", "answer", top_k=3)
    assert len(results) == 1
    assert isinstance(results[0], SearchResult)
    assert results[0].score == pytest.approx(0.92)

    url = str(httpx_mock.get_requests()[0].url)
    assert "q=answer" in url and "max_results=3" in url


@pytest.mark.integration
def test_search_sends_query_params(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/knowledge-bases/kb_1/search?q=x&max_results=5",
        method="POST",
        json={"results": [], "query": "x", "total": 0},
    )
    client.knowledge.search("kb_1", "x")
    url = str(httpx_mock.get_requests()[0].url)
    assert "q=x" in url



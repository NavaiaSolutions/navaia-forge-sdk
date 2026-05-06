"""Tests for the ``client.workforces.edges`` sub-resource."""

from __future__ import annotations

import pytest

from navaia_forge import Edge


@pytest.fixture
def edge_payload() -> dict:
    return {
        "id": "ed_1",
        "workforce_id": "wf_1",
        "source_agent_id": "ag_1",
        "target_agent_id": "ag_2",
        "approval_mode": "auto_run",
        "condition_expr": None,
        "label": "to_review",
        "max_runs": None,
        "task_mode": "sequential",
        "created_at": "2026-01-01T00:00:00Z",
    }


@pytest.mark.integration
def test_edges_create(httpx_mock, client, base_url, edge_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/edges",
        method="POST",
        json=edge_payload,
    )
    edge = client.workforces.edges.create(
        workforce_id="wf_1",
        source_agent_id="ag_1",
        target_agent_id="ag_2",
        label="to_review",
    )
    assert isinstance(edge, Edge)
    assert edge.label == "to_review"

    body = httpx_mock.get_requests()[0].read().decode()
    assert "wf_1" in body and "ag_1" in body and "ag_2" in body


@pytest.mark.integration
def test_edges_update_uses_put(httpx_mock, client, base_url, edge_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/edges/ed_1",
        method="PUT",
        json={**edge_payload, "label": "renamed"},
    )
    edge = client.workforces.edges.update("ed_1", label="renamed")
    assert edge.label == "renamed"


@pytest.mark.integration
def test_edges_delete_returns_none(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/edges/ed_1",
        method="DELETE",
        status_code=204,
    )
    assert client.workforces.edges.delete("ed_1") is None


@pytest.mark.integration
def test_edges_list_uses_full_view(httpx_mock, client, base_url, edge_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/full",
        method="GET",
        json={
            "id": "wf_1",
            "name": "Eng",
            "description": "",
            "runtime_mode": "claude_max",
            "config_json": {},
            "status": "active",
            "agents": [],
            "edges": [edge_payload],
        },
    )
    edges = client.workforces.edges.list("wf_1")
    assert len(edges) == 1
    assert edges[0].id == "ed_1"

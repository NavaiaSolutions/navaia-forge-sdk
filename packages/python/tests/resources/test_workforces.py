"""Smoke tests for the WorkforcesResource."""

from __future__ import annotations

import pytest

from navaia_forge import NavaiaForgeClient, Workforce


@pytest.fixture
def workforce_payload() -> dict:
    return {
        "id": "wf_1",
        "name": "Engineering",
        "description": "Eng team",
        "runtime_mode": "claude_max",
        "config_json": {},
        "status": "active",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
    }


@pytest.mark.integration
def test_list(httpx_mock, client: NavaiaForgeClient, base_url, workforce_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces",
        method="GET",
        json={"items": [workforce_payload], "total": 1},
    )
    result = client.workforces.list()
    assert len(result) == 1
    assert isinstance(result[0], Workforce)
    assert result[0].id == "wf_1"


@pytest.mark.integration
def test_get(httpx_mock, client, base_url, workforce_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1",
        method="GET",
        json=workforce_payload,
    )
    wf = client.workforces.get("wf_1")
    assert wf.name == "Engineering"


@pytest.mark.integration
def test_create_sends_correct_body(httpx_mock, client, base_url, workforce_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces",
        method="POST",
        json=workforce_payload,
    )
    wf = client.workforces.create("Engineering", description="Eng team")
    assert wf.id == "wf_1"
    request = httpx_mock.get_requests()[0]
    body = request.read().decode()
    assert "Engineering" in body
    assert "claude_max" in body  # default runtime_mode


@pytest.mark.integration
def test_delete_returns_none(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1",
        method="DELETE",
        status_code=204,
    )
    assert client.workforces.delete("wf_1") is None

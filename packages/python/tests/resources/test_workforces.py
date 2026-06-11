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
def test_create_with_template_and_config(httpx_mock, client, base_url, workforce_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces",
        method="POST",
        json=workforce_payload,
    )
    wf = client.workforces.create(
        "From template",
        template_id="tpl_1",
        config_json={"key": "value"},
    )
    assert wf.id == "wf_1"
    body = httpx_mock.get_requests()[0].read().decode()
    assert "tpl_1" in body
    assert "value" in body


@pytest.mark.integration
def test_update_uses_put(httpx_mock, client, base_url, workforce_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1",
        method="PUT",
        json={**workforce_payload, "name": "renamed"},
    )
    wf = client.workforces.update("wf_1", name="renamed")
    assert wf.name == "renamed"


@pytest.mark.integration
def test_get_full(httpx_mock, client, base_url, workforce_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/full",
        method="GET",
        json={**workforce_payload, "agents": [], "edges": []},
    )
    full = client.workforces.get_full("wf_1")
    assert full.id == "wf_1"
    assert full.agents == []
    assert full.edges == []


@pytest.mark.integration
def test_delete_returns_none(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1",
        method="DELETE",
        status_code=204,
    )
    assert client.workforces.delete("wf_1") is None


@pytest.mark.integration
def test_publish_sends_listing_payload(httpx_mock, client, base_url, workforce_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/publish",
        method="POST",
        json={
            **workforce_payload,
            "is_public": True,
            "moderation_status": "pending",
            "published_at": "2026-06-11T00:00:00Z",
        },
    )
    wf = client.workforces.publish(
        "wf_1",
        tagline="Ship faster",
        category="engineering",
        price_cents=0,
    )
    assert wf.is_public is True
    assert wf.moderation_status == "pending"
    body = httpx_mock.get_requests()[0].read().decode()
    assert "Ship faster" in body
    assert "engineering" in body
    assert "SAR" in body  # default currency


@pytest.mark.integration
def test_unpublish(httpx_mock, client, base_url, workforce_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/unpublish",
        method="POST",
        json={**workforce_payload, "is_public": False},
    )
    wf = client.workforces.unpublish("wf_1")
    assert wf.is_public is False

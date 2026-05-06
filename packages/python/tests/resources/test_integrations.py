"""Tests for IntegrationsResource."""

from __future__ import annotations

import pytest

from navaia_forge import AvailablePlugin, Integration


@pytest.fixture
def integration_payload() -> dict:
    return {
        "id": "int_1",
        "workforce_id": "wf_1",
        "plugin_name": "slack",
        "display_name": "Slack ops",
        "config_json": {"channel": "#ops"},
        "status": "active",
        "last_error": None,
    }


@pytest.mark.integration
def test_list_plugins(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/plugins",
        method="GET",
        json=[
            {
                "name": "slack",
                "display_name": "Slack",
                "description": "Slack integration",
                "version": "1.0",
                "active": True,
                "config_schema": {"channel": "string"},
            }
        ],
    )
    plugins = client.integrations.list_plugins()
    assert isinstance(plugins[0], AvailablePlugin)
    assert plugins[0].name == "slack"


@pytest.mark.integration
def test_list_integrations(httpx_mock, client, base_url, integration_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/integrations?offset=0&limit=50",
        method="GET",
        json={"items": [integration_payload], "total": 1},
    )
    items = client.integrations.list()
    assert isinstance(items[0], Integration)
    assert items[0].plugin_name == "slack"


@pytest.mark.integration
def test_list_integrations_filtered(
    httpx_mock, client, base_url, integration_payload
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/integrations?offset=0&limit=50&workforce_id=wf_1",
        method="GET",
        json={"items": [integration_payload], "total": 1},
    )
    items = client.integrations.list(workforce_id="wf_1")
    assert items[0].id == "int_1"


@pytest.mark.integration
def test_create_integration(httpx_mock, client, base_url, integration_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/integrations",
        method="POST",
        json=integration_payload,
    )
    integ = client.integrations.create(
        "wf_1", "slack", display_name="Slack ops", config_json={"channel": "#ops"}
    )
    assert integ.status == "active"
    body = httpx_mock.get_requests()[0].read().decode()
    assert "slack" in body
    assert "wf_1" in body


@pytest.mark.integration
def test_update_integration(httpx_mock, client, base_url, integration_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/integrations/int_1",
        method="PUT",
        json={**integration_payload, "display_name": "renamed"},
    )
    integ = client.integrations.update("int_1", display_name="renamed")
    assert integ.display_name == "renamed"


@pytest.mark.integration
def test_delete_integration(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/integrations/int_1",
        method="DELETE",
        status_code=204,
    )
    assert client.integrations.delete("int_1") is None

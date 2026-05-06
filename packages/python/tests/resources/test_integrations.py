"""Smoke tests for IntegrationsResource."""

from __future__ import annotations

import pytest


@pytest.mark.integration
def test_list_integrations(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/integrations",
        method="GET",
        json={
            "items": [
                {
                    "id": "int_1",
                    "workforce_id": "wf_1",
                    "name": "Slack",
                    "type": "slack",
                    "category": "messaging",
                    "status": "connected",
                }
            ],
            "total": 1,
        },
    )
    items = client.integrations.list("wf_1")
    assert items[0].type == "slack"


@pytest.mark.integration
def test_create_integration(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/integrations",
        method="POST",
        json={
            "id": "int_1",
            "workforce_id": "wf_1",
            "name": "Slack",
            "type": "slack",
            "category": "messaging",
            "status": "connected",
        },
    )
    integ = client.integrations.create("wf_1", "Slack", "slack")
    assert integ.status == "connected"

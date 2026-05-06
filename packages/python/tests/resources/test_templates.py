"""Smoke tests for TemplatesResource."""

from __future__ import annotations

import pytest


@pytest.mark.integration
def test_list_templates(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/templates",
        method="GET",
        json={
            "items": [
                {
                    "id": "tpl_1",
                    "name": "Engineering",
                    "category": "dev",
                    "runtime_mode": "claude_max",
                    "is_builtin": True,
                }
            ],
            "total": 1,
        },
    )
    templates = client.templates.list()
    assert templates[0].name == "Engineering"


@pytest.mark.integration
def test_instantiate_returns_workforce(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/templates/tpl_1/instantiate",
        method="POST",
        json={
            "id": "wf_2",
            "name": "My Eng",
            "description": "",
            "runtime_mode": "claude_max",
            "config_json": {},
            "status": "active",
        },
    )
    wf = client.templates.instantiate("tpl_1", "My Eng")
    assert wf.id == "wf_2"

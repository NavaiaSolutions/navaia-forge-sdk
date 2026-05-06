"""Tests for ToolsResource."""

from __future__ import annotations

import pytest

from navaia_forge import Tool, WorkforceToolLink


@pytest.fixture
def tool_payload() -> dict:
    return {
        "id": "tool_1",
        "name": "Slack send",
        "description": "Send a Slack message",
        "kind": "integration",
        "icon": None,
        "integration_id": None,
        "config_json": {},
        "is_featured": False,
        "is_template": False,
    }


@pytest.mark.integration
def test_list(httpx_mock, client, base_url, tool_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/tools",
        method="GET",
        json={"items": [tool_payload], "total": 1},
    )
    tools = client.tools.list()
    assert isinstance(tools[0], Tool)


@pytest.mark.integration
def test_list_featured(httpx_mock, client, base_url, tool_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/tools/featured",
        method="GET",
        json={"items": [tool_payload], "total": 1},
    )
    tools = client.tools.list_featured()
    assert tools[0].id == "tool_1"


@pytest.mark.integration
def test_get(httpx_mock, client, base_url, tool_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/tools/tool_1",
        method="GET",
        json=tool_payload,
    )
    assert client.tools.get("tool_1").name == "Slack send"


@pytest.mark.integration
def test_create(httpx_mock, client, base_url, tool_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/tools",
        method="POST",
        json=tool_payload,
    )
    tool = client.tools.create("Slack send", "integration", description="Send a Slack message")
    assert tool.id == "tool_1"
    body = httpx_mock.get_requests()[0].read().decode()
    assert "Slack send" in body and "integration" in body


@pytest.mark.integration
def test_update_uses_put(httpx_mock, client, base_url, tool_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/tools/tool_1",
        method="PUT",
        json={**tool_payload, "name": "renamed"},
    )
    tool = client.tools.update("tool_1", name="renamed")
    assert tool.name == "renamed"


@pytest.mark.integration
def test_delete(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/tools/tool_1",
        method="DELETE",
        status_code=204,
    )
    assert client.tools.delete("tool_1") is None


@pytest.mark.integration
def test_list_workforce_tools(httpx_mock, client, base_url, tool_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/tools",
        method="GET",
        json=[
            {"tool": tool_payload, "override_json": {"channel": "ops"}, "added_at": "x"}
        ],
    )
    links = client.tools.list_workforce_tools("wf_1")
    assert isinstance(links[0], WorkforceToolLink)
    assert links[0].override_json == {"channel": "ops"}


@pytest.mark.integration
def test_attach_to_workforce(httpx_mock, client, base_url, tool_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/tools",
        method="POST",
        json={"tool": tool_payload, "override_json": {}, "added_at": "x"},
    )
    link = client.tools.attach_to_workforce("wf_1", "tool_1")
    assert link.tool.id == "tool_1"


@pytest.mark.integration
def test_detach_from_workforce(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/tools/tool_1",
        method="DELETE",
        status_code=204,
    )
    assert client.tools.detach_from_workforce("wf_1", "tool_1") is None

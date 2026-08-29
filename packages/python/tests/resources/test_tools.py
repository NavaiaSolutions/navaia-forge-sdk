"""Smoke tests for ToolsResource."""

from __future__ import annotations

import pytest

from navaia_forge import Tool, WorkforceToolLink


@pytest.fixture
def tool_payload() -> dict:
    return {
        "id": "tl_1",
        "owner_id": "usr_1",
        "name": "HTTP GET",
        "description": "",
        "kind": "http",
        "icon": None,
        "integration_id": None,
        "config_json": {},
        "is_featured": False,
        "is_template": False,
    }


@pytest.mark.integration
def test_list_tools(httpx_mock, client, base_url, tool_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/tools",
        method="GET",
        json={"items": [tool_payload], "total": 1},
    )
    tools = client.tools.list()
    assert isinstance(tools[0], Tool)
    assert tools[0].kind == "http"


@pytest.mark.integration
def test_create_tool(httpx_mock, client, base_url, tool_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/tools", method="POST", json=tool_payload
    )
    tool = client.tools.create("HTTP GET", "http", config_json={"url": "x"})
    assert tool.name == "HTTP GET"
    body = httpx_mock.get_requests()[0].read().decode()
    assert "http" in body
    assert "config_json" in body


@pytest.mark.integration
def test_update_tool_uses_put(httpx_mock, client, base_url, tool_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/tools/tl_1",
        method="PUT",
        json={**tool_payload, "name": "Renamed"},
    )
    tool = client.tools.update("tl_1", name="Renamed")
    assert tool.name == "Renamed"


@pytest.mark.integration
def test_delete_tool(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/tools/tl_1", method="DELETE", status_code=204
    )
    assert client.tools.delete("tl_1") is None


@pytest.mark.integration
def test_list_workforce_tools_bare_array(
    httpx_mock, client, base_url, tool_payload
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/tools",
        method="GET",
        json=[{"tool": tool_payload, "override_json": {}, "added_at": None}],
    )
    links = client.tools.list_workforce_tools("wf_1")
    assert isinstance(links[0], WorkforceToolLink)
    assert links[0].tool.id == "tl_1"


@pytest.mark.integration
def test_attach_to_workforce(httpx_mock, client, base_url, tool_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/tools",
        method="POST",
        json={"tool": tool_payload, "override_json": {"k": "v"}, "added_at": None},
    )
    link = client.tools.attach_to_workforce("wf_1", "tl_1", {"k": "v"})
    assert link.override_json == {"k": "v"}
    body = httpx_mock.get_requests()[0].read().decode()
    assert "tool_id" in body

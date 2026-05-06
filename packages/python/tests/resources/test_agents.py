"""Smoke tests for AgentsResource."""

from __future__ import annotations

import pytest

from navaia_forge import Agent, NavaiaForgeClient, WorkforceMember


@pytest.fixture
def agent_payload() -> dict:
    return {
        "id": "ag_1",
        "workforce_id": "wf_1",
        "name": "Researcher",
        "role": "research",
        "instructions": "Find things",
        "model_provider": "anthropic",
        "model_name": "sonnet",
        "max_turns": 25,
    }


@pytest.mark.integration
def test_list_agents_with_filter(httpx_mock, client, base_url, agent_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/agents?workforce_id=wf_1",
        method="GET",
        json={"items": [agent_payload], "total": 1},
    )
    agents = client.agents.list(workforce_id="wf_1")
    assert len(agents) == 1
    assert isinstance(agents[0], Agent)
    assert agents[0].name == "Researcher"


@pytest.mark.integration
def test_create_agent(httpx_mock, client: NavaiaForgeClient, base_url, agent_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/agents",
        method="POST",
        json=agent_payload,
    )
    agent = client.agents.create(
        workforce_id="wf_1",
        name="Researcher",
        role="research",
        instructions="Find things",
    )
    assert agent.id == "ag_1"


@pytest.mark.integration
def test_list_featured_agents(httpx_mock, client, base_url, agent_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/agents/featured",
        method="GET",
        json={"items": [agent_payload], "total": 1},
    )
    agents = client.agents.list_featured()
    assert agents[0].id == "ag_1"


@pytest.mark.integration
def test_get_agent(httpx_mock, client, base_url, agent_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/agents/ag_1",
        method="GET",
        json=agent_payload,
    )
    assert client.agents.get("ag_1").role == "research"


@pytest.mark.integration
def test_update_agent_uses_put(httpx_mock, client, base_url, agent_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/agents/ag_1",
        method="PUT",
        json={**agent_payload, "name": "renamed"},
    )
    agent = client.agents.update("ag_1", name="renamed")
    assert agent.name == "renamed"


@pytest.mark.integration
def test_delete_agent(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/agents/ag_1",
        method="DELETE",
        status_code=204,
    )
    assert client.agents.delete("ag_1") is None


@pytest.mark.integration
def test_clone_agent(httpx_mock, client, base_url, agent_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/agents/ag_1/clone",
        method="POST",
        json={**agent_payload, "id": "ag_2", "name": "Researcher (copy)"},
    )
    cloned = client.agents.clone("ag_1")
    assert cloned.id == "ag_2"


@pytest.mark.integration
def test_clone_agent_with_name(httpx_mock, client, base_url, agent_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/agents/ag_1/clone",
        method="POST",
        json={**agent_payload, "id": "ag_3", "name": "Custom"},
    )
    cloned = client.agents.clone("ag_1", name="Custom")
    body = httpx_mock.get_requests()[0].read().decode()
    assert "Custom" in body
    assert cloned.name == "Custom"


@pytest.mark.integration
def test_export_agent(httpx_mock, client, base_url) -> None:
    export_data = {"agent": {"id": "ag_1", "name": "Researcher"}, "version": 1}
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/agents/ag_1/export",
        method="GET",
        json=export_data,
    )
    result = client.agents.export("ag_1")
    assert result["version"] == 1


@pytest.mark.integration
def test_list_workforce_members(httpx_mock, client, base_url, agent_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/members",
        method="GET",
        json=[
            {
                "agent": agent_payload,
                "override_json": {"max_turns": 50},
                "position_x": 100.0,
                "position_y": 200.0,
            }
        ],
    )
    members = client.agents.list_workforce_members("wf_1")
    assert isinstance(members[0], WorkforceMember)
    assert members[0].agent.id == "ag_1"
    assert members[0].override_json == {"max_turns": 50}


@pytest.mark.integration
def test_attach_member(httpx_mock, client, base_url, agent_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/members",
        method="POST",
        json={
            "agent": agent_payload,
            "override_json": {},
            "position_x": 50.0,
            "position_y": 60.0,
        },
    )
    member = client.agents.attach_to_workforce(
        "wf_1", "ag_1", position_x=50.0, position_y=60.0
    )
    assert member.agent.id == "ag_1"
    assert member.position_x == 50.0


@pytest.mark.integration
def test_detach_member(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/members/ag_1",
        method="DELETE",
        status_code=204,
    )
    assert client.agents.detach_from_workforce("wf_1", "ag_1") is None

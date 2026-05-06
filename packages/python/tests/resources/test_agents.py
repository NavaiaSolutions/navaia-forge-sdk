"""Smoke tests for AgentsResource."""

from __future__ import annotations

import pytest

from navaia_forge import Agent, NavaiaForgeClient


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

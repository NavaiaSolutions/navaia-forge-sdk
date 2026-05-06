"""Tests for TemplatesResource (workforce + agent templates)."""

from __future__ import annotations

import pytest

from navaia_forge import (
    AgentTemplate,
    TemplateInstantiateResult,
    WorkforceTemplate,
)

# ── Workforce templates ─────────────────────────────────────────


@pytest.fixture
def wf_template_payload() -> dict:
    return {
        "id": "tpl_1",
        "name": "Engineering",
        "description": "Eng squad",
        "category": "dev",
        "runtime_mode": "claude_max",
        "agents_config": [],
        "edges_config": [],
        "config_json": {},
        "is_builtin": True,
        "price_cents": 0,
        "is_premium": False,
        "preview_json": {},
    }


@pytest.mark.integration
def test_list_workforce_templates(httpx_mock, client, base_url, wf_template_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforce-templates?offset=0&limit=50",
        method="GET",
        json={"items": [wf_template_payload], "total": 1},
    )
    templates = client.templates.list()
    assert isinstance(templates[0], WorkforceTemplate)
    assert templates[0].name == "Engineering"


@pytest.mark.integration
def test_list_workforce_templates_with_category(
    httpx_mock, client, base_url, wf_template_payload
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforce-templates?category=dev&offset=0&limit=10",
        method="GET",
        json={"items": [wf_template_payload], "total": 1},
    )
    templates = client.templates.list(category="dev", limit=10)
    assert templates[0].id == "tpl_1"


@pytest.mark.integration
def test_get_workforce_template(httpx_mock, client, base_url, wf_template_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforce-templates/tpl_1",
        method="GET",
        json=wf_template_payload,
    )
    assert client.templates.get("tpl_1").name == "Engineering"


@pytest.mark.integration
def test_create_workforce_template(httpx_mock, client, base_url, wf_template_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforce-templates",
        method="POST",
        json=wf_template_payload,
    )
    tpl = client.templates.create(
        "Engineering",
        description="Eng squad",
        runtime_mode="claude_max",
        category="dev",
    )
    assert tpl.id == "tpl_1"
    body = httpx_mock.get_requests()[0].read().decode()
    assert "Engineering" in body and "dev" in body


@pytest.mark.integration
def test_instantiate_returns_summary(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforce-templates/tpl_1/instantiate",
        method="POST",
        json={
            "id": "wf_2",
            "name": "My Eng",
            "description": "Eng squad",
            "agents_created": 3,
            "edges_created": 2,
        },
    )
    result = client.templates.instantiate("tpl_1", "My Eng")
    assert isinstance(result, TemplateInstantiateResult)
    assert result.id == "wf_2"
    assert result.agents_created == 3
    assert result.edges_created == 2


@pytest.mark.integration
def test_delete_workforce_template(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforce-templates/tpl_1",
        method="DELETE",
        status_code=204,
    )
    assert client.templates.delete("tpl_1") is None


# ── Agent templates ─────────────────────────────────────────────


@pytest.fixture
def agent_template_payload() -> dict:
    return {
        "id": "atpl_1",
        "name": "Researcher",
        "role": "research",
        "description": "Web research agent",
        "instructions": "Find facts.",
        "model_provider": "anthropic",
        "model_name": "sonnet",
        "escalation_model": None,
        "max_turns": 25,
        "tools": [],
        "config_json": {},
        "is_builtin": True,
        "category": "research",
    }


@pytest.mark.integration
def test_list_agent_templates(httpx_mock, client, base_url, agent_template_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/agent-templates?offset=0&limit=50",
        method="GET",
        json={"items": [agent_template_payload], "total": 1},
    )
    templates = client.templates.agents.list()
    assert isinstance(templates[0], AgentTemplate)
    assert templates[0].role == "research"


@pytest.mark.integration
def test_get_agent_template(httpx_mock, client, base_url, agent_template_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/agent-templates/atpl_1",
        method="GET",
        json=agent_template_payload,
    )
    assert client.templates.agents.get("atpl_1").name == "Researcher"


@pytest.mark.integration
def test_create_agent_template(httpx_mock, client, base_url, agent_template_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/agent-templates",
        method="POST",
        json=agent_template_payload,
    )
    tpl = client.templates.agents.create(
        "Researcher",
        "research",
        instructions="Find facts.",
        category="research",
    )
    assert tpl.id == "atpl_1"
    body = httpx_mock.get_requests()[0].read().decode()
    assert "Researcher" in body and "research" in body


@pytest.mark.integration
def test_delete_agent_template(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/agent-templates/atpl_1",
        method="DELETE",
        status_code=204,
    )
    assert client.templates.agents.delete("atpl_1") is None

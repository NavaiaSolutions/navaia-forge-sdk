"""Tests for ObservabilityResource (metrics, evals, cost, token usage)."""

from __future__ import annotations

import pytest

from navaia_forge import (
    AgentMetrics,
    CostSummary,
    RLEvaluation,
    TokenUsage,
)

# ── Workforce summary (freeform) ────────────────────────────────


@pytest.mark.integration
def test_workforce_summary_returns_dict(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/metrics",
        method="GET",
        json={"total_tasks": 10, "completed_tasks": 8, "active_agents": 2},
    )
    summary = client.observability.summary("wf_1")
    assert summary["total_tasks"] == 10
    assert summary["active_agents"] == 2


# ── Cost ────────────────────────────────────────────────────────


@pytest.mark.integration
def test_workforce_cost(httpx_mock, client, base_url) -> None:
    payload = {
        "workforce_id": "wf_1",
        "period_days": 7,
        "total_tokens": 1000,
        "total_weighted_tokens": 1500,
        "total_cost_usd": 0.42,
        "by_agent": [
            {
                "agent_id": "ag_1",
                "agent_name": "Researcher",
                "total_tokens": 1000,
                "weighted_tokens": 1500,
                "cost_usd": 0.42,
                "call_count": 5,
            }
        ],
        "by_model": [
            {
                "model": "claude-sonnet",
                "total_tokens": 1000,
                "weighted_tokens": 1500,
                "cost_usd": 0.42,
                "call_count": 5,
            }
        ],
    }
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/cost?days=7",
        method="GET",
        json=payload,
    )
    cost = client.observability.cost("wf_1", days=7)
    assert isinstance(cost, CostSummary)
    assert cost.total_cost_usd == 0.42
    assert cost.by_agent[0].agent_id == "ag_1"
    assert cost.by_model[0].model == "claude-sonnet"


# ── Agent metrics ───────────────────────────────────────────────


@pytest.mark.integration
def test_agent_metrics(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/agents/ag_1/metrics?period=daily&limit=30",
        method="GET",
        json=[
            {
                "id": "m_1",
                "agent_id": "ag_1",
                "period": "daily",
                "period_start": "2026-05-01T00:00:00Z",
                "tasks_completed": 5,
                "tasks_failed": 1,
                "avg_duration_ms": 1200.5,
                "total_tokens": 5000,
                "total_cost_usd": 0.10,
                "quality_score": 0.92,
                "created_at": "2026-05-01T00:00:00Z",
            }
        ],
    )
    metrics = client.observability.agent_metrics("ag_1")
    assert isinstance(metrics[0], AgentMetrics)
    assert metrics[0].tasks_completed == 5


# ── Agent evaluations ───────────────────────────────────────────


@pytest.mark.integration
def test_agent_evaluations(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/agents/ag_1/evaluations?limit=5",
        method="GET",
        json=[
            {
                "id": "e_1",
                "agent_id": "ag_1",
                "batch": 1,
                "score_delta": 0.05,
                "cumulative_score": 0.85,
                "quality_rating": 4,
                "token_efficiency": 0.7,
                "summary": "Good run",
                "created_at": "2026-05-01T00:00:00Z",
            }
        ],
    )
    evals = client.observability.agent_evaluations("ag_1", limit=5)
    assert isinstance(evals[0], RLEvaluation)
    assert evals[0].quality_rating == 4


# ── Token usage logging ─────────────────────────────────────────


@pytest.mark.integration
def test_log_token_usage(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/token-usage",
        method="POST",
        json={
            "id": "tu_1",
            "agent_id": "ag_1",
            "task_id": None,
            "model": "claude-sonnet",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "weighted_tokens": 200,
            "cost_usd": 0.001,
            "duration_ms": 1234,
            "date_key": "2026-05-06",
            "created_at": "2026-05-06T12:00:00Z",
        },
    )
    usage = client.observability.log_token_usage(
        model="claude-sonnet",
        agent_id="ag_1",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.001,
    )
    assert isinstance(usage, TokenUsage)
    assert usage.total_tokens == 150
    body = httpx_mock.get_requests()[0].read().decode()
    assert "claude-sonnet" in body
    assert "ag_1" in body

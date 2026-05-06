"""Smoke tests for ObservabilityResource."""

from __future__ import annotations

import pytest


@pytest.mark.integration
def test_summary(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/metrics",
        method="GET",
        json={
            "total_tasks": 10,
            "completed_tasks": 8,
            "failed_tasks": 1,
            "active_agents": 2,
            "total_tokens_today": 1234,
            "cost_today": 0.5,
            "tasks_by_status": {"done": 8, "failed": 1, "pending": 1},
            "tokens_by_agent": [],
            "tokens_by_model": [],
            "tasks_over_time": [],
            "cost_over_time": [],
        },
    )
    summary = client.observability.summary("wf_1")
    assert summary.total_tasks == 10
    assert summary.completed_tasks == 8


@pytest.mark.integration
def test_token_usage_includes_days_param(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/metrics/tokens?days=14",
        method="GET",
        json={"items": [], "total": 0},
    )
    result = client.observability.token_usage("wf_1", days=14)
    assert result == []

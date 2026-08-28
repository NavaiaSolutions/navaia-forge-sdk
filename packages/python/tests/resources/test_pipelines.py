"""Smoke tests for PipelinesResource."""

from __future__ import annotations

import pytest

from navaia_forge import Pipeline, PipelineRun


@pytest.fixture
def pipeline_payload() -> dict:
    return {
        "id": "pl_1",
        "workforce_id": "wf_1",
        "name": "Nightly report",
        "description": "",
        "config_json": {"steps": []},
        "status": "active",
    }


@pytest.fixture
def run_payload() -> dict:
    return {
        "id": "run_1",
        "pipeline_id": "pl_1",
        "status": "pending",
        "result": None,
        "error": None,
    }


@pytest.mark.integration
def test_list_pipelines(httpx_mock, client, base_url, pipeline_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/pipelines",
        method="GET",
        json={"items": [pipeline_payload], "total": 1},
    )
    pipelines = client.pipelines.list()
    assert isinstance(pipelines[0], Pipeline)
    assert pipelines[0].id == "pl_1"


@pytest.mark.integration
def test_list_pipelines_scoped_to_workforce(
    httpx_mock, client, base_url, pipeline_payload
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/pipelines",
        method="GET",
        json=[pipeline_payload],  # bare array — transport tolerates both shapes
    )
    pipelines = client.pipelines.list("wf_1")
    assert pipelines[0].workforce_id == "wf_1"


@pytest.mark.integration
def test_create_pipeline(httpx_mock, client, base_url, pipeline_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/pipelines",
        method="POST",
        json=pipeline_payload,
    )
    pipeline = client.pipelines.create(
        "Nightly report", workforce_id="wf_1", config_json={"steps": []}
    )
    assert pipeline.name == "Nightly report"
    body = httpx_mock.get_requests()[0].read().decode()
    assert "workforce_id" in body
    assert "config_json" in body


@pytest.mark.integration
def test_run_pipeline(httpx_mock, client, base_url, run_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/pipelines/pl_1/run",
        method="POST",
        json=run_payload,
    )
    run = client.pipelines.run("pl_1")
    assert isinstance(run, PipelineRun)
    assert run.pipeline_id == "pl_1"
    assert run.status == "pending"


@pytest.mark.integration
def test_list_runs_with_limit(httpx_mock, client, base_url, run_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/pipelines/pl_1/runs?limit=5",
        method="GET",
        json={"items": [run_payload], "total": 1},
    )
    runs = client.pipelines.list_runs("pl_1", limit=5)
    assert runs[0].id == "run_1"


@pytest.mark.integration
def test_report_run(httpx_mock, client, base_url, run_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/pipelines/pl_1/runs",
        method="POST",
        json={**run_payload, "status": "done", "result": "ok"},
    )
    run = client.pipelines.report_run("pl_1", {"status": "done", "result": "ok"})
    assert run.status == "done"
    assert run.result == "ok"

"""Smoke tests for TasksResource."""

from __future__ import annotations

import pytest

from navaia_forge import NavaiaForgeError, Task


@pytest.fixture
def task_payload() -> dict:
    return {
        "id": "tk_1",
        "workforce_id": "wf_1",
        "agent_id": None,
        "title": "Review PR",
        "description": "",
        "status": "pending",
        "priority": "standard",
        "source": "api",
        "result": None,
        "error": None,
        "retry_count": 0,
        "metadata_json": {},
    }


@pytest.mark.integration
def test_create_task_returns_typed_model(httpx_mock, client, base_url, task_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/tasks",
        method="POST",
        json=task_payload,
    )
    task = client.tasks.create(workforce_id="wf_1", title="Review PR")
    assert isinstance(task, Task)
    assert task.status == "pending"


@pytest.mark.integration
def test_get_task(httpx_mock, client, base_url, task_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/tasks/tk_1",
        method="GET",
        json=task_payload,
    )
    task = client.tasks.get("tk_1")
    assert task.id == "tk_1"


@pytest.mark.integration
def test_wait_for_completion_polls_until_done(
    httpx_mock, client, base_url, task_payload
) -> None:
    pending = {**task_payload, "status": "pending"}
    done = {**task_payload, "status": "done"}
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/tasks/tk_1", method="GET", json=pending,
    )
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/tasks/tk_1", method="GET", json=done,
    )
    final = client.tasks.wait_for_completion(
        "tk_1", poll_interval=0.0, timeout=2.0
    )
    assert final.status == "done"


@pytest.mark.integration
def test_approve_task(httpx_mock, client, base_url, task_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/tasks/tk_1/approve",
        method="POST",
        json={**task_payload, "status": "in_progress"},
    )
    task = client.tasks.approve("tk_1")
    assert task.status == "in_progress"


@pytest.mark.integration
def test_list_tasks(httpx_mock, client, base_url, task_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/tasks",
        method="GET",
        json={"items": [task_payload], "total": 1},
    )
    tasks = client.tasks.list("wf_1")
    assert tasks[0].id == "tk_1"


@pytest.mark.integration
def test_list_tasks_with_status(httpx_mock, client, base_url, task_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/tasks?status=done",
        method="GET",
        json={"items": [{**task_payload, "status": "done"}], "total": 1},
    )
    tasks = client.tasks.list("wf_1", status="done")
    assert tasks[0].status == "done"


@pytest.mark.integration
def test_create_task_with_agent_and_metadata(
    httpx_mock, client, base_url, task_payload
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/tasks",
        method="POST",
        json={**task_payload, "agent_id": "ag_1", "metadata_json": {"k": "v"}},
    )
    task = client.tasks.create(
        workforce_id="wf_1",
        title="Review PR",
        agent_id="ag_1",
        metadata={"k": "v"},
    )
    assert task.agent_id == "ag_1"
    body = httpx_mock.get_requests()[0].read().decode()
    assert "ag_1" in body
    assert "metadata_json" in body


@pytest.mark.integration
def test_reject_task(httpx_mock, client, base_url, task_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/tasks/tk_1/reject",
        method="POST",
        # The backend maps rejection to CANCELLED (see tasks/service.py reject_task).
        json={**task_payload, "status": "cancelled", "error": "not needed"},
    )
    task = client.tasks.reject("tk_1", reason="not needed")
    assert task.status == "cancelled"
    assert task.error == "not needed"


@pytest.mark.integration
def test_wait_for_completion_times_out(
    httpx_mock, client, base_url, task_payload
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/tasks/tk_1",
        method="GET",
        json={**task_payload, "status": "pending"},
        is_reusable=True,
    )
    with pytest.raises(NavaiaForgeError):
        client.tasks.wait_for_completion("tk_1", poll_interval=0.0, timeout=0.05)

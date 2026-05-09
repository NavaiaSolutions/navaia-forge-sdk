"""Task resource."""

from __future__ import annotations

import time
from typing import Any

from ..errors import TimeoutError as NfTimeoutError
from ..types import Task, TaskStatus
from ._base import ResourceBase, parse_list, parse_model

_TERMINAL_STATES: frozenset[str] = frozenset({"done", "failed", "rejected"})


class TasksResource(ResourceBase):
    """CRUD + helper operations for tasks."""

    def list(
        self, workforce_id: str, *, status: TaskStatus | str | None = None
    ) -> list[Task]:
        """List tasks for a workforce, optionally filtered by status."""
        params: dict[str, Any] = {}
        if status is not None:
            params["status"] = status
        return parse_list(
            Task,
            self._http.get_list(
                f"/workforces/{workforce_id}/tasks",
                params=params or None,
            ),
        )

    def get(self, task_id: str) -> Task:
        """Fetch a single task by id."""
        return parse_model(Task, self._http.get(f"/tasks/{task_id}"))

    def create(
        self,
        workforce_id: str,
        title: str,
        *,
        description: str = "",
        agent_id: str | None = None,
        priority: str = "standard",
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        """Create a task."""
        body: dict[str, Any] = {
            "workforce_id": workforce_id,
            "title": title,
            "description": description,
            "priority": priority,
        }
        if agent_id is not None:
            body["agent_id"] = agent_id
        if metadata is not None:
            body["metadata_json"] = metadata
        return parse_model(
            Task, self._http.post(f"/workforces/{workforce_id}/tasks", body)
        )

    def approve(self, task_id: str) -> Task:
        """Approve a task that is waiting on human approval."""
        return parse_model(Task, self._http.post(f"/tasks/{task_id}/approve"))

    def reject(self, task_id: str, reason: str = "") -> Task:
        """Reject a task awaiting approval, with optional reason."""
        return parse_model(
            Task, self._http.post(f"/tasks/{task_id}/reject", {"reason": reason})
        )

    def retry(self, task_id: str) -> Task:
        """Retry a failed task."""
        return parse_model(Task, self._http.post(f"/tasks/{task_id}/retry"))

    def wait_for_completion(
        self,
        task_id: str,
        *,
        poll_interval: float = 5.0,
        timeout: float = 300.0,
    ) -> Task:
        """Poll until the task reaches a terminal state.

        Raises:
            TimeoutError: If the task does not reach a terminal state in time.
        """
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            task = self.get(task_id)
            if task.status in _TERMINAL_STATES:
                return task
            time.sleep(poll_interval)
        raise NfTimeoutError(f"Task {task_id} did not complete within {timeout}s")

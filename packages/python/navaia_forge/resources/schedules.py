"""Schedule resource — run an agent on a cron expression."""

from __future__ import annotations

from typing import Any

from ..types import Schedule
from ._base import ResourceBase, parse_list, parse_model


class SchedulesResource(ResourceBase):
    """CRUD for recurring task definitions.

    A schedule binds a cron expression to **one agent**. The backend's
    scheduler loop wakes on an interval, finds every enabled schedule whose
    ``next_run_at`` has passed, and submits a task for it with
    ``source="scheduler"`` — so a schedule is how work starts without anyone
    calling :meth:`tasks.create`.

    ``next_run_at`` is server-computed from ``cron_expr`` and ``timezone`` and
    advances after each run; it cannot be set by the caller.
    """

    def list(self, workforce_id: str) -> list[Schedule]:
        """Every schedule on a workforce, enabled or not."""
        return parse_list(
            Schedule, self._http.get_list(f"/workforces/{workforce_id}/schedules")
        )

    def create(
        self,
        workforce_id: str,
        agent_id: str,
        title: str,
        cron_expr: str,
        *,
        description: str = "",
        timezone: str = "Asia/Riyadh",
        priority: str = "standard",
        enabled: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> Schedule:
        """Create a schedule.

        ``title`` and ``description`` become the title and description of every
        task the schedule submits, so ``description`` is where the recurring
        instruction goes.

        ``cron_expr`` is a five-field expression evaluated in ``timezone``.
        """
        body: dict[str, Any] = {
            "agent_id": agent_id,
            "title": title,
            "description": description,
            "cron_expr": cron_expr,
            "timezone": timezone,
            "priority": priority,
            "enabled": enabled,
        }
        if metadata is not None:
            body["metadata_json"] = metadata
        return parse_model(
            Schedule, self._http.post(f"/workforces/{workforce_id}/schedules", body)
        )

    def update(
        self,
        schedule_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        cron_expr: str | None = None,
        timezone: str | None = None,
        priority: str | None = None,
        enabled: bool | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Schedule:
        """Change a schedule. Only the fields you pass are sent."""
        body: dict[str, Any] = {}
        for key, value in (
            ("title", title),
            ("description", description),
            ("cron_expr", cron_expr),
            ("timezone", timezone),
            ("priority", priority),
            ("enabled", enabled),
            ("metadata_json", metadata),
        ):
            if value is not None:
                body[key] = value
        return parse_model(Schedule, self._http.patch(f"/schedules/{schedule_id}", body))

    def pause(self, schedule_id: str) -> Schedule:
        """Stop a schedule firing, keeping its definition."""
        return self.update(schedule_id, enabled=False)

    def resume(self, schedule_id: str) -> Schedule:
        """Let a paused schedule fire again."""
        return self.update(schedule_id, enabled=True)

    def delete(self, schedule_id: str) -> None:
        """Remove a schedule."""
        self._http.delete(f"/schedules/{schedule_id}")

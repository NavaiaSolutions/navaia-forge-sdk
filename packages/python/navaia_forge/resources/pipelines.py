"""Pipeline resource.

CRUD, run triggering, and run history for pipelines. Mirrors the JavaScript
``nf.pipelines`` resource and the platform's ``/pipelines`` API.
"""

from __future__ import annotations

from typing import Any

from ..types import Pipeline, PipelineRun
from ._base import ResourceBase, parse_list, parse_model


class PipelinesResource(ResourceBase):
    """CRUD + run operations for pipelines."""

    # ── CRUD ───────────────────────────────────────────────────

    def list(self, workforce_id: str | None = None) -> list[Pipeline]:
        """List pipelines, optionally scoped to a single workforce."""
        path = (
            f"/workforces/{workforce_id}/pipelines"
            if workforce_id is not None
            else "/pipelines"
        )
        return parse_list(Pipeline, self._http.get_list(path))

    def get(self, pipeline_id: str) -> Pipeline:
        """Fetch a single pipeline by id."""
        return parse_model(Pipeline, self._http.get(f"/pipelines/{pipeline_id}"))

    def create(
        self,
        name: str,
        *,
        workforce_id: str | None = None,
        description: str = "",
        config_json: dict[str, Any] | None = None,
    ) -> Pipeline:
        """Create a pipeline."""
        body: dict[str, Any] = {"name": name, "description": description}
        if workforce_id is not None:
            body["workforce_id"] = workforce_id
        if config_json is not None:
            body["config_json"] = config_json
        return parse_model(Pipeline, self._http.post("/pipelines", body))

    def update(
        self,
        pipeline_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        config_json: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> Pipeline:
        """Patch a pipeline. Only the provided fields are sent."""
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if config_json is not None:
            body["config_json"] = config_json
        if status is not None:
            body["status"] = status
        return parse_model(
            Pipeline, self._http.patch(f"/pipelines/{pipeline_id}", body)
        )

    def delete(self, pipeline_id: str) -> None:
        """Delete a pipeline."""
        self._http.delete(f"/pipelines/{pipeline_id}")

    # ── Runs ───────────────────────────────────────────────────

    def run(self, pipeline_id: str) -> PipelineRun:
        """Trigger a run of the pipeline."""
        return parse_model(
            PipelineRun, self._http.post(f"/pipelines/{pipeline_id}/run")
        )

    def list_runs(
        self, pipeline_id: str, *, limit: int | None = None
    ) -> list[PipelineRun]:
        """List a pipeline's run history (newest first)."""
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        return parse_list(
            PipelineRun,
            self._http.get_list(
                f"/pipelines/{pipeline_id}/runs", params=params or None
            ),
        )

    def report_run(
        self,
        pipeline_id: str,
        *,
        status: str,
        result: str | None = None,
        error: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> PipelineRun:
        """Report an externally-executed run back to the platform (runner ingest).

        Used by out-of-band runners to record the outcome of a run they executed
        themselves, rather than triggering one via :meth:`run`. Fields mirror the
        JS ``PipelineRunReport`` body; only provided fields are sent.
        """
        body: dict[str, Any] = {"status": status}
        if result is not None:
            body["result"] = result
        if error is not None:
            body["error"] = error
        if metadata_json is not None:
            body["metadata_json"] = metadata_json
        return parse_model(
            PipelineRun, self._http.post(f"/pipelines/{pipeline_id}/runs", body)
        )

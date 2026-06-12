"""Two-way workforce sync between a local backend and the Fareegi cloud.

The :class:`SyncResource` exports a self-contained :class:`WorkforceSyncBundle`
from one instance and imports it into another. Because the SDK client is the
orchestrator (the two backends never talk to each other), :meth:`push` and
:meth:`pull` simply chain an export on one client with an import on the other.

Identity is carried by ``origin_id`` on every entity, so a workforce can make a
full round-trip (push to cloud, edit in the cloud UI, pull back) without ever
duplicating. See ``docs/SYNC_ARCHITECTURE_PLAN.md`` for the normative spec.

409 handling is local to this resource: the generic transport in
:mod:`navaia_forge.http` collapses error bodies into a string, which would lose
the ``remote_bundle`` the server returns on conflict. So :meth:`import_bundle`
issues a raw request and parses the conflict body itself, raising
:class:`SyncConflictError` carrying both the local and remote bundles.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from ..errors import NavaiaForgeError, SyncConflictError, error_from_status
from ..types import SyncImportResult, WorkforceSyncBundle
from ._base import ResourceBase, parse_model

if TYPE_CHECKING:
    from ..client import NavaiaForgeClient


class SyncResource(ResourceBase):
    """Export, import, push, and pull workforce bundles across instances."""

    # ── Export ─────────────────────────────────────────────────

    def export_bundle(
        self,
        workforce_id: str,
        *,
        include_tasks: bool = False,
        include_conversations: bool = False,
    ) -> WorkforceSyncBundle:
        """Export a workforce and all its children as a portable bundle.

        Runtime data (tasks, conversations) is excluded by default to keep
        bundles small; opt in with ``include_tasks`` / ``include_conversations``.
        """
        params: dict[str, Any] = {
            "include_tasks": include_tasks,
            "include_conversations": include_conversations,
        }
        payload = self._http.get(f"/sync/export/{workforce_id}", params=params)
        return parse_model(WorkforceSyncBundle, payload)

    # ── Import ─────────────────────────────────────────────────

    def import_bundle(
        self,
        bundle: WorkforceSyncBundle | dict[str, Any],
        *,
        force: bool = False,
    ) -> SyncImportResult:
        """Import a bundle into this instance, creating or updating in place.

        Raises :class:`SyncConflictError` (HTTP 409) when the target was
        modified since the last sync and ``force`` is not set; the raised error
        carries both ``local_bundle`` (the bundle you tried to import) and
        ``remote_bundle`` (the server's current state) so the caller can decide
        which side wins.
        """
        body = (
            bundle.model_dump(mode="json")
            if isinstance(bundle, WorkforceSyncBundle)
            else bundle
        )
        payload = self._post_import(body, force=force, local_bundle=bundle)
        return parse_model(SyncImportResult, payload)

    def _post_import(
        self,
        body: dict[str, Any],
        *,
        force: bool,
        local_bundle: WorkforceSyncBundle | dict[str, Any],
    ) -> Any:
        """Raw POST to ``/sync/import`` that preserves the 409 conflict body."""
        url = self._http._build_url("/sync/import")
        headers = self._http._build_headers({"Content-Type": "application/json"})
        try:
            response = self._http._client.post(
                url,
                json=body,
                params={"force": str(force).lower()},
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            raise NavaiaForgeError(0, f"Request timed out: {exc}") from exc
        except httpx.RequestError as exc:
            raise NavaiaForgeError(0, f"Network error: {exc}") from exc

        if response.status_code == 409:
            raise self._conflict_error(response, local_bundle)

        if not response.is_success:
            try:
                data = response.json()
                detail = data.get("detail") or data.get("error") or response.text
            except ValueError:
                detail = response.text or response.reason_phrase
            raise error_from_status(response.status_code, str(detail))

        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise NavaiaForgeError(
                response.status_code, f"Invalid JSON in response: {exc}"
            ) from exc

    @staticmethod
    def _conflict_error(
        response: httpx.Response,
        local_bundle: WorkforceSyncBundle | dict[str, Any],
    ) -> SyncConflictError:
        """Build a :class:`SyncConflictError` from a 409 response body.

        The backend wraps the conflict payload in FastAPI's ``detail`` key,
        so the body is ``{"detail": {"error": ..., "remote_bundle": {...}}}``.
        We also accept a flat ``{"error": ..., "remote_bundle": {...}}`` shape
        for resilience to transport changes.
        """
        remote_bundle: WorkforceSyncBundle | None = None
        message = "Remote was modified since last sync"
        try:
            data = response.json()
        except ValueError:
            data = None

        # Unwrap the FastAPI ``detail`` envelope when present.
        inner: dict[str, Any] = {}
        if isinstance(data, dict):
            detail = data.get("detail")
            if isinstance(detail, dict):
                inner = detail
            elif isinstance(detail, str):
                message = detail
                inner = data
            else:
                inner = data

        raw_remote = inner.get("remote_bundle")
        if isinstance(raw_remote, dict):
            try:
                remote_bundle = parse_model(WorkforceSyncBundle, raw_remote)
            except Exception:
                remote_bundle = None
        if message == "Remote was modified since last sync":
            err = inner.get("error")
            if isinstance(err, str) and err:
                message = err
        return SyncConflictError(
            message,
            local_bundle=local_bundle,
            remote_bundle=remote_bundle,
        )

    # ── Orchestrated push / pull ───────────────────────────────

    def push(
        self,
        workforce_id: str,
        *,
        remote: NavaiaForgeClient,
        force: bool = False,
        include_tasks: bool = False,
        include_conversations: bool = False,
    ) -> SyncImportResult:
        """Export from this instance and import into ``remote`` (e.g. cloud)."""
        bundle = self.export_bundle(
            workforce_id,
            include_tasks=include_tasks,
            include_conversations=include_conversations,
        )
        return remote.sync.import_bundle(bundle, force=force)

    def pull(
        self,
        workforce_id: str,
        *,
        remote: NavaiaForgeClient,
        force: bool = False,
        include_tasks: bool = False,
        include_conversations: bool = False,
    ) -> SyncImportResult:
        """Export from ``remote`` (e.g. cloud) and import into this instance."""
        bundle = remote.sync.export_bundle(
            workforce_id,
            include_tasks=include_tasks,
            include_conversations=include_conversations,
        )
        return self.import_bundle(bundle, force=force)

    # ── Disk round-trip ────────────────────────────────────────

    def export_to_file(
        self,
        workforce_id: str,
        path: str | Path,
        *,
        include_tasks: bool = False,
        include_conversations: bool = False,
    ) -> WorkforceSyncBundle:
        """Export a workforce bundle and write it to ``path`` as JSON."""
        bundle = self.export_bundle(
            workforce_id,
            include_tasks=include_tasks,
            include_conversations=include_conversations,
        )
        Path(path).write_text(
            json.dumps(bundle.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return bundle

    def import_from_file(
        self,
        path: str | Path,
        *,
        force: bool = False,
    ) -> SyncImportResult:
        """Read a bundle JSON file from ``path`` and import it."""
        raw = Path(path).read_text(encoding="utf-8")
        bundle = parse_model(WorkforceSyncBundle, json.loads(raw))
        return self.import_bundle(bundle, force=force)

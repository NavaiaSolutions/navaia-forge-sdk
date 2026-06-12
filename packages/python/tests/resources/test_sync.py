"""Tests for the SyncResource (export/import/push/pull + disk round-trip)."""

from __future__ import annotations

import json

import pytest

from navaia_forge import (
    NavaiaForgeClient,
    SyncConflictError,
    SyncImportResult,
    WorkforceSyncBundle,
)


@pytest.fixture
def bundle_payload() -> dict:
    """A minimal but valid WorkforceSyncBundle JSON body."""
    return {
        "bundle_version": "1.0",
        "exported_at": "2026-06-12T00:00:00Z",
        "instance_id": "inst_local",
        "content_hash": "abc123",
        "workforce": {
            "origin_id": "inst_local:wf_1",
            "name": "Life OS",
            "description": "Personal assistant",
            "runtime_mode": "claude_max",
            "config_json": {},
            "status": "active",
        },
        "agents": [
            {
                "origin_id": "inst_local:ag_1",
                "name": "Fitness Coach",
                "role": "coach",
                "instructions": "Track workouts",
            }
        ],
        "edges": [],
        "tasks": [],
        "conversations": [],
        "knowledge_bases": [],
        "integrations": [],
    }


@pytest.fixture
def import_result_payload() -> dict:
    return {
        "workforce_id": "wf_new",
        "action": "created",
        "agents": {"created": 1, "updated": 0, "deleted": 0},
        "edges": {"created": 0, "updated": 0, "deleted": 0},
        "knowledge_bases": {"created": 0, "updated": 0, "deleted": 0},
        "integrations": {"created": 0, "updated": 0, "deleted": 0},
        "tasks_imported": 0,
        "conversations_imported": 0,
        "integrations_require_setup": [],
    }


@pytest.fixture
def cloud() -> NavaiaForgeClient:
    return NavaiaForgeClient(
        base_url="http://cloud.local", api_key="nf_cloud", timeout=5.0
    )


# ── Export ─────────────────────────────────────────────────


@pytest.mark.integration
def test_export_bundle(httpx_mock, client, base_url, bundle_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/sync/export/wf_1?include_tasks=False&include_conversations=False",
        method="GET",
        json=bundle_payload,
    )
    bundle = client.sync.export_bundle("wf_1")
    assert isinstance(bundle, WorkforceSyncBundle)
    assert bundle.workforce.origin_id == "inst_local:wf_1"
    assert bundle.agents[0].name == "Fitness Coach"


@pytest.mark.integration
def test_export_bundle_with_runtime_data(
    httpx_mock, client, base_url, bundle_payload
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/sync/export/wf_1?include_tasks=True&include_conversations=True",
        method="GET",
        json=bundle_payload,
    )
    client.sync.export_bundle(
        "wf_1", include_tasks=True, include_conversations=True
    )
    request = httpx_mock.get_requests()[0]
    assert "include_tasks=True" in str(request.url)
    assert "include_conversations=True" in str(request.url)


# ── Import ─────────────────────────────────────────────────


@pytest.mark.integration
def test_import_bundle_created(
    httpx_mock, client, base_url, bundle_payload, import_result_payload
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/sync/import?force=false",
        method="POST",
        status_code=201,
        json=import_result_payload,
    )
    bundle = WorkforceSyncBundle.model_validate(bundle_payload)
    result = client.sync.import_bundle(bundle)
    assert isinstance(result, SyncImportResult)
    assert result.action == "created"
    assert result.agents.created == 1


@pytest.mark.integration
def test_import_bundle_accepts_dict(
    httpx_mock, client, base_url, bundle_payload, import_result_payload
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/sync/import?force=false",
        method="POST",
        status_code=200,
        json=import_result_payload,
    )
    result = client.sync.import_bundle(bundle_payload)
    assert result.workforce_id == "wf_new"


@pytest.mark.integration
def test_import_bundle_force_sets_query(
    httpx_mock, client, base_url, bundle_payload, import_result_payload
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/sync/import?force=true",
        method="POST",
        status_code=200,
        json=import_result_payload,
    )
    client.sync.import_bundle(bundle_payload, force=True)
    assert "force=true" in str(httpx_mock.get_requests()[0].url)


@pytest.mark.integration
def test_import_bundle_conflict_raises_with_both_bundles(
    httpx_mock, client, base_url, bundle_payload
) -> None:
    remote = {**bundle_payload, "instance_id": "inst_cloud", "content_hash": "zzz"}
    # Backend wraps the conflict payload in FastAPI's ``detail`` envelope.
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/sync/import?force=false",
        method="POST",
        status_code=409,
        json={"detail": {"error": "sync_conflict", "remote_bundle": remote}},
    )
    bundle = WorkforceSyncBundle.model_validate(bundle_payload)
    with pytest.raises(SyncConflictError) as exc_info:
        client.sync.import_bundle(bundle)
    err = exc_info.value
    assert err.status_code == 409
    assert err.local_bundle is bundle
    assert isinstance(err.remote_bundle, WorkforceSyncBundle)
    assert err.remote_bundle.instance_id == "inst_cloud"


@pytest.mark.integration
def test_import_bundle_maps_other_errors(
    httpx_mock, client, base_url, bundle_payload
) -> None:
    from navaia_forge import ValidationError

    httpx_mock.add_response(
        url=f"{base_url}/api/v1/sync/import?force=false",
        method="POST",
        status_code=422,
        json={"detail": "count mismatch"},
    )
    with pytest.raises(ValidationError):
        client.sync.import_bundle(bundle_payload)


# ── Push / Pull (two-client orchestration) ─────────────────


@pytest.mark.integration
def test_push_exports_local_imports_remote(
    httpx_mock, client, cloud, bundle_payload, import_result_payload
) -> None:
    httpx_mock.add_response(
        url="http://test.local/api/v1/sync/export/wf_1?include_tasks=False&include_conversations=False",
        method="GET",
        json=bundle_payload,
    )
    httpx_mock.add_response(
        url="http://cloud.local/api/v1/sync/import?force=false",
        method="POST",
        status_code=201,
        json=import_result_payload,
    )
    result = client.sync.push("wf_1", remote=cloud)
    assert result.action == "created"


@pytest.mark.integration
def test_pull_exports_remote_imports_local(
    httpx_mock, client, cloud, bundle_payload, import_result_payload
) -> None:
    httpx_mock.add_response(
        url="http://cloud.local/api/v1/sync/export/wf_9?include_tasks=False&include_conversations=False",
        method="GET",
        json=bundle_payload,
    )
    httpx_mock.add_response(
        url="http://test.local/api/v1/sync/import?force=false",
        method="POST",
        status_code=200,
        json=import_result_payload,
    )
    result = client.sync.pull("wf_9", remote=cloud)
    assert result.workforce_id == "wf_new"


# ── Disk round-trip ────────────────────────────────────────


@pytest.mark.integration
def test_export_to_file_writes_json(
    httpx_mock, client, base_url, bundle_payload, tmp_path
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/sync/export/wf_1?include_tasks=False&include_conversations=False",
        method="GET",
        json=bundle_payload,
    )
    out = tmp_path / "bundle.json"
    client.sync.export_to_file("wf_1", out)
    written = json.loads(out.read_text())
    assert written["workforce"]["origin_id"] == "inst_local:wf_1"


@pytest.mark.integration
def test_import_from_file_reads_and_imports(
    httpx_mock, client, base_url, bundle_payload, import_result_payload, tmp_path
) -> None:
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(bundle_payload))
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/sync/import?force=false",
        method="POST",
        status_code=201,
        json=import_result_payload,
    )
    result = client.sync.import_from_file(path)
    assert result.action == "created"

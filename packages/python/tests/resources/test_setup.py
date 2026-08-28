"""Smoke tests for SetupResource."""

from __future__ import annotations

import pytest

from navaia_forge import SetupOptions, SetupValidateResult


@pytest.mark.integration
def test_options(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/setup/options",
        method="GET",
        json={"navaia_cloud_enabled": True, "claude_cli_enabled": False},
    )
    opts = client.setup.options()
    assert isinstance(opts, SetupOptions)
    assert opts.navaia_cloud_enabled is True


@pytest.mark.integration
def test_validate(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/setup/validate",
        method="POST",
        json={"status": "healthy", "message": "ok"},
    )
    result = client.setup.validate("api_key", {"api_key": "sk-..."})
    assert isinstance(result, SetupValidateResult)
    assert result.status == "healthy"
    body = httpx_mock.get_requests()[0].read().decode()
    assert "setup_path" in body


@pytest.mark.integration
def test_complete(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/setup/complete",
        method="POST",
        json={"onboarding_completed": True},
    )
    result = client.setup.complete()
    assert result["onboarding_completed"] is True

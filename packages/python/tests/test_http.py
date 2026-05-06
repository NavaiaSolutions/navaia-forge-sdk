"""Tests for the HTTP transport: URL building, headers, error mapping."""

from __future__ import annotations

import pytest

from navaia_forge import HttpClient, HttpConfig, NotFoundError, ValidationError


@pytest.mark.unit
def test_build_url_prepends_api_v1(base_url: str) -> None:
    http = HttpClient(HttpConfig(base_url=base_url, api_key="k", timeout=1.0))
    assert http._build_url("/workforces") == f"{base_url}/api/v1/workforces"


@pytest.mark.unit
def test_build_headers_includes_api_key(base_url: str) -> None:
    http = HttpClient(HttpConfig(base_url=base_url, api_key="my-key", timeout=1.0))
    headers = http._build_headers()
    assert headers["X-API-Key"] == "my-key"
    assert headers["Accept"] == "application/json"


@pytest.mark.unit
def test_build_headers_omits_api_key_when_blank(base_url: str) -> None:
    http = HttpClient(HttpConfig(base_url=base_url, api_key="", timeout=1.0))
    assert "X-API-Key" not in http._build_headers()


@pytest.mark.integration
def test_request_maps_404_to_not_found(httpx_mock, base_url: str) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/missing",
        status_code=404,
        json={"detail": "no such workforce"},
    )
    http = HttpClient(HttpConfig(base_url=base_url, api_key="k", timeout=5.0))
    with pytest.raises(NotFoundError) as exc:
        http.get("/workforces/missing")
    assert "no such workforce" in str(exc.value)


@pytest.mark.integration
def test_request_maps_422_to_validation_error(httpx_mock, base_url: str) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/agents",
        status_code=422,
        json={"detail": "name required"},
    )
    http = HttpClient(HttpConfig(base_url=base_url, api_key="k", timeout=5.0))
    with pytest.raises(ValidationError):
        http.post("/agents", {})


@pytest.mark.integration
def test_get_list_unwraps_paginated_envelope(httpx_mock, base_url: str) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces",
        status_code=200,
        json={"items": [{"id": "1"}, {"id": "2"}], "total": 2},
    )
    http = HttpClient(HttpConfig(base_url=base_url, api_key="k", timeout=5.0))
    items = http.get_list("/workforces")
    assert items == [{"id": "1"}, {"id": "2"}]


@pytest.mark.integration
def test_204_returns_none(httpx_mock, base_url: str) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/agents/abc",
        method="DELETE",
        status_code=204,
    )
    http = HttpClient(HttpConfig(base_url=base_url, api_key="k", timeout=5.0))
    assert http.delete("/agents/abc") is None

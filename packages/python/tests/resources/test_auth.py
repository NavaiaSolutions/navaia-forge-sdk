"""Tests for AuthResource."""

from __future__ import annotations

import pytest

from navaia_forge import ApiKeyCreated, ApiKeyValidation, TokenPair, User


def _user_payload() -> dict:
    return {
        "id": "user_1",
        "email": "alice@example.com",
        "name": "Alice",
        "avatar_url": None,
        "provider": "email",
        "is_admin": False,
        "onboarding_completed": True,
        "created_at": "2025-01-01T00:00:00Z",
    }


def _token_payload() -> dict:
    return {
        "access_token": "access-xyz",
        "refresh_token": "refresh-xyz",
        "token_type": "bearer",
        "user": _user_payload(),
    }


@pytest.mark.integration
def test_me(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/auth/me",
        method="GET",
        json=_user_payload(),
    )
    me = client.auth.me()
    assert isinstance(me, User)
    assert me.id == "user_1"
    assert me.email == "alice@example.com"
    assert me.onboarding_completed is True


@pytest.mark.integration
def test_register(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/auth/register",
        method="POST",
        json=_token_payload(),
    )
    pair = client.auth.register(name="Alice", email="alice@example.com", password="pw1")
    assert isinstance(pair, TokenPair)
    assert pair.access_token == "access-xyz"
    assert pair.user.email == "alice@example.com"
    body = httpx_mock.get_requests()[0].read().decode()
    assert "alice@example.com" in body
    assert "pw1" in body


@pytest.mark.integration
def test_login(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/auth/login",
        method="POST",
        json=_token_payload(),
    )
    pair = client.auth.login(email="alice@example.com", password="pw1")
    assert pair.refresh_token == "refresh-xyz"
    body = httpx_mock.get_requests()[0].read().decode()
    assert "alice@example.com" in body


@pytest.mark.integration
def test_refresh(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/auth/refresh",
        method="POST",
        json=_token_payload(),
    )
    pair = client.auth.refresh("refresh-xyz")
    assert pair.access_token == "access-xyz"
    body = httpx_mock.get_requests()[0].read().decode()
    assert "refresh-xyz" in body


@pytest.mark.integration
def test_create_key(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/auth/keys",
        method="POST",
        json={
            "api_key": "nf_secret_xyz",
            "key_hash": "hash-xyz",
            "name": "ci",
            "message": "Store this key securely; it will not be shown again.",
        },
    )
    created = client.auth.create_key("ci")
    assert isinstance(created, ApiKeyCreated)
    assert created.api_key == "nf_secret_xyz"
    assert created.name == "ci"
    body = httpx_mock.get_requests()[0].read().decode()
    assert "ci" in body


@pytest.mark.integration
def test_validate(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/auth/validate",
        method="GET",
        json={"valid": True, "user_id": "user_1", "role": "admin"},
    )
    result = client.auth.validate()
    assert isinstance(result, ApiKeyValidation)
    assert result.valid is True
    assert result.user_id == "user_1"


@pytest.mark.unit
def test_oauth_login_urls(client, base_url) -> None:
    assert client.auth.google_login_url() == f"{base_url}/api/v1/auth/google"
    assert client.auth.github_login_url() == f"{base_url}/api/v1/auth/github"

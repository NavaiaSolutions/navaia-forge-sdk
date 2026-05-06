"""Shared pytest fixtures for the SDK test suite."""

from __future__ import annotations

import pytest

from navaia_forge import NavaiaForgeClient

BASE_URL = "http://test.local"
API_KEY = "nf_test_key"


@pytest.fixture
def client() -> NavaiaForgeClient:
    """Construct an SDK client pointed at the mock transport."""
    return NavaiaForgeClient(base_url=BASE_URL, api_key=API_KEY, timeout=5.0)


@pytest.fixture
def base_url() -> str:
    return BASE_URL


@pytest.fixture
def api_key() -> str:
    return API_KEY

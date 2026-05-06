"""Unit tests for the error hierarchy."""

from __future__ import annotations

import pytest

from navaia_forge import (
    AuthenticationError,
    NavaiaForgeError,
    NotFoundError,
    PermissionError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from navaia_forge.errors import error_from_status


@pytest.mark.unit
@pytest.mark.parametrize(
    "status, expected",
    [
        (401, AuthenticationError),
        (403, PermissionError),
        (404, NotFoundError),
        (422, ValidationError),
        (429, RateLimitError),
        (500, ServerError),
        (503, ServerError),
        (418, NavaiaForgeError),
    ],
)
def test_error_from_status_returns_specific_subclass(
    status: int, expected: type[NavaiaForgeError]
) -> None:
    err = error_from_status(status, "boom")
    assert isinstance(err, expected)
    assert err.status_code == status
    assert "boom" in str(err)


@pytest.mark.unit
def test_all_subclasses_inherit_from_base() -> None:
    for cls in (
        AuthenticationError,
        PermissionError,
        NotFoundError,
        ValidationError,
        RateLimitError,
    ):
        assert issubclass(cls, NavaiaForgeError)

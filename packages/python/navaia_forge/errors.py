"""Exception hierarchy for the NavaiaForge SDK.

All SDK errors derive from :class:`NavaiaForgeError` so callers can catch them
with a single ``except NavaiaForgeError`` clause. HTTP status codes are mapped
to specific subclasses by :func:`error_from_status`.
"""

from __future__ import annotations


class NavaiaForgeError(Exception):
    """Base exception for all NavaiaForge SDK errors."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"HTTP {status_code}: {message}" if status_code else message)


class AuthenticationError(NavaiaForgeError):
    """Raised when authentication fails (HTTP 401)."""

    def __init__(self, message: str = "Invalid or missing API key") -> None:
        super().__init__(401, message)


class PermissionError(NavaiaForgeError):
    """Raised when the caller lacks permission (HTTP 403)."""

    def __init__(self, message: str = "Permission denied") -> None:
        super().__init__(403, message)


class NotFoundError(NavaiaForgeError):
    """Raised when a resource is not found (HTTP 404)."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(404, message)


class ValidationError(NavaiaForgeError):
    """Raised when the server rejects a request body (HTTP 422)."""

    def __init__(self, message: str = "Validation failed") -> None:
        super().__init__(422, message)


class RateLimitError(NavaiaForgeError):
    """Raised when the rate limit is exceeded (HTTP 429)."""

    def __init__(self, message: str = "Rate limit exceeded") -> None:
        super().__init__(429, message)


class ServerError(NavaiaForgeError):
    """Raised on 5xx server errors."""

    def __init__(self, status_code: int, message: str = "Server error") -> None:
        super().__init__(status_code, message)


class TimeoutError(NavaiaForgeError):
    """Raised when a polling operation exceeds its timeout."""

    def __init__(self, message: str) -> None:
        super().__init__(0, message)


def error_from_status(status_code: int, message: str) -> NavaiaForgeError:
    """Map an HTTP status code to the appropriate :class:`NavaiaForgeError` subclass."""
    if status_code == 401:
        return AuthenticationError(message)
    if status_code == 403:
        return PermissionError(message)
    if status_code == 404:
        return NotFoundError(message)
    if status_code == 422:
        return ValidationError(message)
    if status_code == 429:
        return RateLimitError(message)
    if 500 <= status_code < 600:
        return ServerError(status_code, message)
    return NavaiaForgeError(status_code, message)

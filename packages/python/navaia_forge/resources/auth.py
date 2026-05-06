"""Auth resource — register / login / refresh / me / api-keys / validate.

All endpoints live under ``/api/v1/auth/*``. Note that login and registration
return JWT tokens; SDK callers usually authenticate with a long-lived API key
(via ``X-API-Key`` set on :class:`HttpClient`), but the JWT flow is exposed
here so callers can build a UI on top of the SDK.
"""

from __future__ import annotations

from typing import Any

from ..types import ApiKeyCreated, ApiKeyValidation, TokenPair, User
from ._base import ResourceBase, parse_model


class AuthResource(ResourceBase):
    """Authentication, profile, and API-key operations."""

    # ── Profile ──────────────────────────────────────────────────

    def me(self) -> User:
        """Return the currently authenticated user's profile."""
        return parse_model(User, self._http.get("/auth/me"))

    # ── Email / password flows ───────────────────────────────────

    def register(self, *, name: str, email: str, password: str) -> TokenPair:
        """Register a new email/password user."""
        return parse_model(
            TokenPair,
            self._http.post(
                "/auth/register",
                {"name": name, "email": email, "password": password},
            ),
        )

    def login(self, *, email: str, password: str) -> TokenPair:
        """Log in with email and password."""
        return parse_model(
            TokenPair,
            self._http.post(
                "/auth/login",
                {"email": email, "password": password},
            ),
        )

    def refresh(self, refresh_token: str) -> TokenPair:
        """Exchange a refresh token for a new access/refresh pair."""
        return parse_model(
            TokenPair,
            self._http.post("/auth/refresh", {"refresh_token": refresh_token}),
        )

    # ── API keys ─────────────────────────────────────────────────

    def create_key(self, name: str = "default") -> ApiKeyCreated:
        """Generate a new API key.

        The plaintext ``api_key`` is shown exactly once — store it securely.
        """
        return parse_model(
            ApiKeyCreated,
            self._http.post("/auth/keys", {"name": name}),
        )

    def validate(self) -> ApiKeyValidation:
        """Validate the current API key (or JWT) attached to the client."""
        return parse_model(ApiKeyValidation, self._http.get("/auth/validate"))

    # ── OAuth (helpers — return URLs for UI to redirect to) ──────

    def google_login_url(self) -> str:
        """Return the Google OAuth start URL (``GET /auth/google``)."""
        return self._oauth_start_url("google")

    def github_login_url(self) -> str:
        """Return the GitHub OAuth start URL (``GET /auth/github``)."""
        return self._oauth_start_url("github")

    def _oauth_start_url(self, provider: str) -> str:
        """Build an absolute URL the caller can redirect a browser to."""
        # The HTTP client owns the base URL + ``/api/v1`` prefix; reach into it
        # via the public ``base_url`` accessor pattern used elsewhere.
        config: Any = getattr(self._http, "_config", None)
        base = getattr(config, "base_url", "").rstrip("/")
        return f"{base}/api/v1/auth/{provider}"

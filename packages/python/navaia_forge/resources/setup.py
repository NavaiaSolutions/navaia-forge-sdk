"""Setup / onboarding wizard resource.

Wraps ``/api/v1/setup/*``: query which onboarding paths are available, run a
connectivity check for a chosen path, and mark onboarding as complete.
"""

from __future__ import annotations

from typing import Any

from ..types import SetupOptions, SetupValidateResult
from ._base import ResourceBase, parse_model


class SetupResource(ResourceBase):
    """Operations for the onboarding/setup wizard."""

    def options(self) -> SetupOptions:
        """Fetch which onboarding paths are enabled in this deployment."""
        return parse_model(SetupOptions, self._http.get("/setup/options"))

    def validate(
        self,
        setup_path: str,
        *,
        config: dict[str, Any] | None = None,
    ) -> SetupValidateResult:
        """Run the connectivity check for an onboarding path.

        ``setup_path`` is one of ``navaia_cloud``, ``claude_subscription``,
        ``api_key``, ``self_hosted``, ``custom_endpoint``. ``config`` is the
        path-specific config dict (empty for cloud/subscription paths).
        """
        body: dict[str, Any] = {
            "setup_path": setup_path,
            "config": config or {},
        }
        return parse_model(
            SetupValidateResult, self._http.post("/setup/validate", body)
        )

    def complete(self) -> dict[str, Any]:
        """Mark the current user's onboarding as completed."""
        result = self._http.post("/setup/complete", None)
        return result if isinstance(result, dict) else {}

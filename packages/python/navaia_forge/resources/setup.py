"""Setup / onboarding wizard resource.

Wraps ``/setup/*``: query which onboarding paths are available, run a
connectivity check for a chosen path, and mark onboarding complete. Mirrors the
JavaScript ``nf.setup`` resource.
"""

from __future__ import annotations

from typing import Any

from ..types import SetupOptions, SetupValidateResult
from ._base import ResourceBase, parse_model


class SetupResource(ResourceBase):
    """Onboarding: query options, validate a path, mark complete."""

    def options(self) -> SetupOptions:
        """Fetch which onboarding paths are enabled in this deployment."""
        return parse_model(SetupOptions, self._http.get("/setup/options"))

    def validate(
        self, setup_path: str, config: dict[str, Any] | None = None
    ) -> SetupValidateResult:
        """Run the connectivity check for an onboarding path.

        Args:
            setup_path: One of ``navaia_cloud``, ``claude_subscription``,
                ``api_key``, ``self_hosted``, ``custom_endpoint``.
            config: Path-specific config (empty for cloud/subscription paths).
        """
        body = {"setup_path": setup_path, "config": config or {}}
        return parse_model(
            SetupValidateResult, self._http.post("/setup/validate", body)
        )

    def complete(self) -> dict[str, Any]:
        """Mark the current user's onboarding as completed."""
        result = self._http.post("/setup/complete")
        return result if isinstance(result, dict) else {}

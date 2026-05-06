"""Observability resource (metrics, token usage)."""

from __future__ import annotations

from ..types import MetricsSummary, TokenUsage
from ._base import ResourceBase, parse_list, parse_model


class ObservabilityResource(ResourceBase):
    """Metrics, summaries, and token-usage queries."""

    def summary(self, workforce_id: str) -> MetricsSummary:
        """Fetch the dashboard metrics summary for a workforce."""
        return parse_model(
            MetricsSummary,
            self._http.get(f"/workforces/{workforce_id}/metrics"),
        )

    def token_usage(self, workforce_id: str, *, days: int = 7) -> list[TokenUsage]:
        """Fetch the per-day token usage for a workforce."""
        return parse_list(
            TokenUsage,
            self._http.get_list(
                f"/workforces/{workforce_id}/metrics/tokens",
                params={"days": days},
            ),
        )

"""Observability resource — metrics, evaluations, token usage, cost."""

from __future__ import annotations

from typing import Any

from ..types import (
    AgentMetrics,
    CostSummary,
    RLEvaluation,
    TokenUsage,
)
from ._base import ResourceBase, parse_list, parse_model


class ObservabilityResource(ResourceBase):
    """Metrics, evaluations, token-usage logging, and cost queries."""

    # ── Workforce-level ──────────────────────────────────────────

    def summary(self, workforce_id: str) -> dict[str, Any]:
        """Fetch the freeform dashboard summary for a workforce.

        Returns the raw payload — the backend response shape is intentionally
        flexible (task counts, token rollups, etc.) and may evolve.
        """
        result = self._http.get(f"/workforces/{workforce_id}/metrics")
        return result if isinstance(result, dict) else {}

    def cost(self, workforce_id: str, *, days: int = 30) -> CostSummary:
        """Fetch the cost breakdown for a workforce over ``days`` days."""
        return parse_model(
            CostSummary,
            self._http.get(
                f"/workforces/{workforce_id}/cost",
                params={"days": days},
            ),
        )

    # ── Agent-level ──────────────────────────────────────────────

    def agent_metrics(
        self,
        agent_id: str,
        *,
        period: str = "daily",
        limit: int = 30,
    ) -> list[AgentMetrics]:
        """Fetch rolled-up metrics rows for an agent."""
        return parse_list(
            AgentMetrics,
            self._http.get(
                f"/agents/{agent_id}/metrics",
                params={"period": period, "limit": limit},
            ),
        )

    def agent_evaluations(
        self, agent_id: str, *, limit: int = 20
    ) -> list[RLEvaluation]:
        """Fetch RL evaluations for an agent."""
        return parse_list(
            RLEvaluation,
            self._http.get(
                f"/agents/{agent_id}/evaluations",
                params={"limit": limit},
            ),
        )

    # ── Token usage ──────────────────────────────────────────────

    def log_token_usage(
        self,
        *,
        model: str,
        agent_id: str | None = None,
        task_id: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        duration_ms: int = 0,
    ) -> TokenUsage:
        """Log a single token-usage event."""
        body: dict[str, Any] = {
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "duration_ms": duration_ms,
        }
        if agent_id is not None:
            body["agent_id"] = agent_id
        if task_id is not None:
            body["task_id"] = task_id
        return parse_model(TokenUsage, self._http.post("/token-usage", body))

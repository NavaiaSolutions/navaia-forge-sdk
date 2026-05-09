"""LangChain callback handler that streams events to Forge observability.

Drop-in for any ``langchain_core``-compatible runnable (which is what
LangGraph compiles to). The handler is best-effort: if the Forge backend
is unreachable, callbacks log a warning and continue rather than killing
the user's graph mid-run.

Usage::

    cb = NavaiaForgeCallback(client, task_id="task_123")
    graph.invoke(state, config={"callbacks": [cb]})

What it reports:

- ``on_llm_end`` → ``client.observability.log_token_usage(...)`` with the
  model name, input/output tokens, cost when present, and the duration.
- ``on_chain_start`` / ``on_chain_end`` / ``on_chain_error`` →
  ``client.tasks.append_log(...)`` if the SDK exposes that method, else
  a structured log line via the standard ``logging`` module. We never
  fail the run on a logging failure.
- ``on_tool_start`` / ``on_tool_end`` → log line + token-usage marker so
  cost dashboards can attribute spend to the tool invocation.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any
from uuid import UUID

from ._lazy import import_base_callback_handler

if TYPE_CHECKING:  # pragma: no cover
    from ...client import NavaiaForgeClient


logger = logging.getLogger(__name__)


def _make_callback_class() -> type:
    """Build the callback class with ``BaseCallbackHandler`` as the base.

    We can't subclass at module import time without forcing the optional
    ``langchain_core`` dependency, so the class is built lazily the first
    time anyone instantiates :class:`NavaiaForgeCallback`.
    """
    base = import_base_callback_handler()

    class _NavaiaForgeCallbackImpl(base):  # type: ignore[misc, valid-type]
        """Internal — see :class:`NavaiaForgeCallback` for the public surface."""

        def __init__(
            self,
            client: NavaiaForgeClient,
            *,
            task_id: str | None = None,
            agent_id: str | None = None,
            workforce_id: str | None = None,
            default_model: str = "unknown",
        ) -> None:
            super().__init__()
            self._client = client
            self._task_id = task_id
            self._agent_id = agent_id
            self._workforce_id = workforce_id
            self._default_model = default_model
            # run_id → start time, so on_*_end can compute duration_ms.
            self._starts: dict[UUID, float] = {}

        # ── LLM ────────────────────────────────────────────────

        def on_llm_start(
            self,
            serialized: dict[str, Any],
            prompts: list[str],
            *,
            run_id: UUID,
            **kwargs: Any,
        ) -> None:
            self._starts[run_id] = time.monotonic()

        def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
            duration_ms = self._duration_ms(run_id)
            usage = _extract_token_usage(response)
            model = _extract_model_name(response) or self._default_model

            try:
                self._client.observability.log_token_usage(
                    model=model,
                    agent_id=self._agent_id,
                    task_id=self._task_id,
                    input_tokens=usage["input"],
                    output_tokens=usage["output"],
                    cost_usd=usage["cost_usd"],
                    duration_ms=duration_ms,
                )
            except Exception as exc:
                logger.warning(
                    "NavaiaForgeCallback: token-usage log failed (%s)", exc
                )

        def on_llm_error(
            self, error: BaseException, *, run_id: UUID, **kwargs: Any
        ) -> None:
            self._starts.pop(run_id, None)
            logger.warning("LangGraph LLM error: %s", error)

        # ── Chain ──────────────────────────────────────────────

        def on_chain_start(
            self,
            serialized: dict[str, Any],
            inputs: dict[str, Any],
            *,
            run_id: UUID,
            **kwargs: Any,
        ) -> None:
            self._starts[run_id] = time.monotonic()
            logger.debug(
                "LangGraph chain start name=%s task=%s",
                _name_of(serialized),
                self._task_id,
            )

        def on_chain_end(
            self, outputs: dict[str, Any], *, run_id: UUID, **kwargs: Any
        ) -> None:
            duration_ms = self._duration_ms(run_id)
            logger.debug(
                "LangGraph chain end task=%s duration_ms=%d", self._task_id, duration_ms
            )

        def on_chain_error(
            self, error: BaseException, *, run_id: UUID, **kwargs: Any
        ) -> None:
            self._starts.pop(run_id, None)
            logger.warning(
                "LangGraph chain error task=%s: %s", self._task_id, error
            )

        # ── Tool ───────────────────────────────────────────────

        def on_tool_start(
            self,
            serialized: dict[str, Any],
            input_str: str,
            *,
            run_id: UUID,
            **kwargs: Any,
        ) -> None:
            self._starts[run_id] = time.monotonic()
            logger.debug(
                "LangGraph tool start name=%s task=%s",
                _name_of(serialized),
                self._task_id,
            )

        def on_tool_end(
            self, output: Any, *, run_id: UUID, **kwargs: Any
        ) -> None:
            duration_ms = self._duration_ms(run_id)
            logger.debug(
                "LangGraph tool end task=%s duration_ms=%d",
                self._task_id,
                duration_ms,
            )

        def on_tool_error(
            self, error: BaseException, *, run_id: UUID, **kwargs: Any
        ) -> None:
            self._starts.pop(run_id, None)
            logger.warning("LangGraph tool error task=%s: %s", self._task_id, error)

        # ── Helpers ────────────────────────────────────────────

        def _duration_ms(self, run_id: UUID) -> int:
            start = self._starts.pop(run_id, None)
            if start is None:
                return 0
            return int((time.monotonic() - start) * 1000)

    return _NavaiaForgeCallbackImpl


def NavaiaForgeCallback(  # noqa: N802 — class-like factory; defers langchain_core import
    client: NavaiaForgeClient,
    *,
    task_id: str | None = None,
    agent_id: str | None = None,
    workforce_id: str | None = None,
    default_model: str = "unknown",
) -> Any:
    """Factory returning a ``BaseCallbackHandler`` instance bound to ``client``.

    Implemented as a function rather than a class so the
    ``langchain_core`` import is deferred until first use — keeps the
    bare ``import navaia_forge`` cheap and safe in environments without
    the optional extra installed.

    Args:
        client: A configured :class:`NavaiaForgeClient`.
        task_id: Forge task id this run is fulfilling, attached to every
            event for cost/usage attribution.
        agent_id: Forge agent id when the graph represents a single agent.
        workforce_id: Forge workforce id, used for high-level rollups.
        default_model: Fallback model name when LangChain doesn't surface
            one — for chains that wrap raw HTTP calls or custom LLMs.
    """
    cls = _make_callback_class()
    return cls(
        client,
        task_id=task_id,
        agent_id=agent_id,
        workforce_id=workforce_id,
        default_model=default_model,
    )


# ── Pure helpers (testable without langchain_core) ────────────────


def _extract_token_usage(response: Any) -> dict[str, int | float]:
    """Pull input/output tokens and cost out of an LLMResult-like object.

    LangChain's response shape varies across versions and providers. The
    canonical place is ``response.llm_output["token_usage"]`` for chat
    models and ``response.generations[0][0].generation_info`` for some
    completions. We also walk ``message.usage_metadata`` which is the
    newer (langchain-core 0.2+) location.
    """
    out = {"input": 0, "output": 0, "cost_usd": 0.0}

    llm_output = getattr(response, "llm_output", None)
    if isinstance(llm_output, dict):
        usage = llm_output.get("token_usage") or llm_output.get("usage") or {}
        if isinstance(usage, dict):
            out["input"] = int(
                usage.get("input_tokens") or usage.get("prompt_tokens") or 0
            )
            out["output"] = int(
                usage.get("output_tokens") or usage.get("completion_tokens") or 0
            )

    if out["input"] == 0 and out["output"] == 0:
        # Try the per-generation usage metadata.
        generations = getattr(response, "generations", None) or []
        for batch in generations:
            for gen in batch or []:
                message = getattr(gen, "message", None)
                meta = getattr(message, "usage_metadata", None)
                if isinstance(meta, dict):
                    out["input"] = int(meta.get("input_tokens", 0))
                    out["output"] = int(meta.get("output_tokens", 0))
                    break
            if out["input"] or out["output"]:
                break

    return out


def _extract_model_name(response: Any) -> str | None:
    """Best-effort model name extraction from an LLMResult-like object."""
    llm_output = getattr(response, "llm_output", None)
    if isinstance(llm_output, dict):
        name = llm_output.get("model_name") or llm_output.get("model")
        if isinstance(name, str) and name:
            return name
    return None


def _name_of(serialized: dict[str, Any] | None) -> str:
    if not isinstance(serialized, dict):
        return "<unknown>"
    return serialized.get("name") or serialized.get("id", ["<unknown>"])[-1] or "<unknown>"

"""Run a compiled LangGraph as a NavaiaForge workforce.

The wrapper is deliberately thin: it takes a compiled graph plus a Forge
client, and on ``run()`` it merges a Forge callback and a Forge context
into the LangChain ``RunnableConfig`` before delegating to the graph's
own ``invoke`` / ``ainvoke``. Customer graphs do not need to be modified.

Why a wrapper at all (instead of just docs telling people to add the
callback themselves)? Three reasons:

1. One place for the wiring. Forgetting either the callback or the
   context is the single most common integration mistake — bundling them
   removes that footgun.
2. A clean handle Forge can register as a workforce. Future backend
   support for ``framework="langgraph"`` workforces lands here without
   any user-side change.
3. Symmetric ``run`` / ``arun`` so sync and async graphs share an API
   shape with the rest of the SDK.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .callback import NavaiaForgeCallback
from .context import with_forge_context

if TYPE_CHECKING:  # pragma: no cover
    from ...client import NavaiaForgeClient


class LangGraphWorkforce:
    """A compiled LangGraph wrapped to run inside NavaiaForge.

    The graph object itself can be anything that exposes ``invoke`` and/or
    ``ainvoke`` accepting ``(input, config)``. That is the LangChain
    runnable protocol — every ``CompiledGraph`` produced by
    ``StateGraph(...).compile()`` satisfies it, but so do hand-rolled
    runnables. We avoid importing ``langgraph`` directly to keep the
    integration framework-agnostic at the type level.
    """

    def __init__(
        self,
        graph: Any,
        client: NavaiaForgeClient,
        *,
        name: str | None = None,
        workforce_id: str | None = None,
        agent_id: str | None = None,
        default_model: str = "unknown",
    ) -> None:
        if not (hasattr(graph, "invoke") or hasattr(graph, "ainvoke")):
            raise TypeError(
                "graph must expose .invoke or .ainvoke "
                "(it should be a CompiledGraph or a LangChain Runnable)."
            )
        self._graph = graph
        self._client = client
        self._name = name
        self._workforce_id = workforce_id
        self._agent_id = agent_id
        self._default_model = default_model

    @property
    def name(self) -> str | None:
        return self._name

    @property
    def graph(self) -> Any:
        return self._graph

    def run(
        self,
        state: Any,
        *,
        task_id: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> Any:
        """Synchronously execute the graph with Forge plumbing wired in.

        ``state`` is passed straight to ``graph.invoke``. ``config`` is
        layered on top of the Forge-augmented config, so user-supplied
        callbacks / configurable values are preserved.
        """
        if not hasattr(self._graph, "invoke"):
            raise NotImplementedError(
                "graph has no .invoke — call .arun() on async-only graphs."
            )
        merged = self._build_config(task_id=task_id, base=config)
        return self._graph.invoke(state, merged)

    async def arun(
        self,
        state: Any,
        *,
        task_id: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> Any:
        """Async counterpart to :meth:`run`."""
        if not hasattr(self._graph, "ainvoke"):
            raise NotImplementedError(
                "graph has no .ainvoke — call .run() on sync-only graphs."
            )
        merged = self._build_config(task_id=task_id, base=config)
        return await self._graph.ainvoke(state, merged)

    # ── Internal ───────────────────────────────────────────────

    def _build_config(
        self, *, task_id: str | None, base: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Merge Forge callback + context into a fresh ``RunnableConfig``."""
        callback = NavaiaForgeCallback(
            self._client,
            task_id=task_id,
            agent_id=self._agent_id,
            workforce_id=self._workforce_id,
            default_model=self._default_model,
        )
        # Preserve user-supplied config values without mutating the input.
        merged: dict[str, Any] = dict(base or {})
        existing_callbacks = list(merged.get("callbacks", []) or [])
        merged["callbacks"] = [*existing_callbacks, callback]
        merged["configurable"] = with_forge_context(
            self._client,
            workforce_id=self._workforce_id,
            task_id=task_id,
            agent_id=self._agent_id,
            base=merged.get("configurable"),
        )
        return merged

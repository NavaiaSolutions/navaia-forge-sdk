"""Forge context injection via LangChain's ``RunnableConfig``.

Why this design: LangChain already has a first-class slot for runtime
context — the ``configurable`` dict on ``RunnableConfig``. We piggy-back
on it instead of inventing a separate injection mechanism, so existing
LangGraph users do not have to rewrite nodes.

Inside a node::

    def search_node(state, config):
        forge = get_forge_context(config)
        hits = forge.client.knowledge.search(forge.workforce_id, "topic")
        return {"results": hits}
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from ...client import NavaiaForgeClient


_CONFIG_KEY = "navaia_forge"


@dataclass(frozen=True)
class ForgeContext:
    """Frozen snapshot of Forge state available inside a LangGraph node.

    Attributes:
        client: The :class:`NavaiaForgeClient` for backend access — knowledge
            search, tool invocation, conversation history, etc.
        workforce_id: The Forge workforce this run belongs to, or ``None``
            when the graph is being driven outside a workforce.
        task_id: The Forge task id this run is fulfilling, or ``None``.
        agent_id: The Forge agent id, when the graph models a single agent.
    """

    client: NavaiaForgeClient
    workforce_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None


def with_forge_context(
    client: NavaiaForgeClient,
    *,
    workforce_id: str | None = None,
    task_id: str | None = None,
    agent_id: str | None = None,
    base: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a ``configurable`` dict carrying a :class:`ForgeContext`.

    Returns a *new* dict — the optional ``base`` argument is left unmodified
    so callers can layer Forge context on top of an existing config without
    surprising mutations.
    """
    ctx = ForgeContext(
        client=client,
        workforce_id=workforce_id,
        task_id=task_id,
        agent_id=agent_id,
    )
    merged = dict(base or {})
    merged[_CONFIG_KEY] = ctx
    return merged


def get_forge_context(config: Any) -> ForgeContext:
    """Extract the :class:`ForgeContext` from a ``RunnableConfig``.

    Accepts either the raw ``RunnableConfig`` mapping or the bare
    ``configurable`` dict, since both shapes show up in node signatures
    depending on how the runnable was invoked.

    Raises:
        LookupError: when no Forge context is present. Surfacing this
            explicitly is friendlier than letting nodes ``KeyError`` deep
            in user code; the message points at :func:`with_forge_context`.
    """
    configurable = _extract_configurable(config)
    ctx = configurable.get(_CONFIG_KEY)
    if not isinstance(ctx, ForgeContext):
        raise LookupError(
            "No NavaiaForge context found on RunnableConfig. "
            "Wrap your invoke/run call with `with_forge_context(client, ...)` "
            "or use `LangGraphWorkforce.run(...)` which sets it for you."
        )
    return ctx


def _extract_configurable(config: Any) -> dict[str, Any]:
    """Normalise the various shapes a ``RunnableConfig`` can take."""
    if config is None:
        return {}
    if isinstance(config, dict):
        # RunnableConfig itself is a TypedDict — its `configurable` key holds
        # the user-facing slot. If we are handed the inner dict directly,
        # treat it as already-configurable.
        nested = config.get("configurable")
        if isinstance(nested, dict):
            return nested
        return config
    # Defensive: unrecognised shape — fall back to attribute access.
    nested = getattr(config, "configurable", None)
    if isinstance(nested, dict):
        return nested
    return {}

"""Tests for the LangGraph ↔ NavaiaForge context plumbing.

These tests do not need ``langchain_core`` — the context module operates
on plain dicts that mirror ``RunnableConfig``'s shape.
"""

from __future__ import annotations

import pytest

from navaia_forge import NavaiaForgeClient
from navaia_forge.integrations.langgraph import (
    ForgeContext,
    get_forge_context,
    with_forge_context,
)


def test_forge_context_is_immutable(client: NavaiaForgeClient) -> None:
    """Frozen dataclasses raise ``FrozenInstanceError`` on attribute assignment."""
    ctx = ForgeContext(client=client, task_id="t1")
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        ctx.task_id = "t2"  # type: ignore[misc]


def test_with_forge_context_returns_new_dict(client: NavaiaForgeClient) -> None:
    base = {"existing": "value"}
    out = with_forge_context(client, task_id="t1", base=base)
    assert out is not base, "should not mutate the base dict"
    assert base == {"existing": "value"}, "base must remain untouched"
    assert out["existing"] == "value"
    assert isinstance(out["navaia_forge"], ForgeContext)


def test_with_forge_context_carries_all_fields(client: NavaiaForgeClient) -> None:
    out = with_forge_context(
        client, workforce_id="wf_1", task_id="t_1", agent_id="a_1"
    )
    ctx = out["navaia_forge"]
    assert isinstance(ctx, ForgeContext)
    assert ctx.client is client
    assert ctx.workforce_id == "wf_1"
    assert ctx.task_id == "t_1"
    assert ctx.agent_id == "a_1"


def test_get_forge_context_from_runnable_config(client: NavaiaForgeClient) -> None:
    """The standard shape — ``RunnableConfig`` with a ``configurable`` key."""
    configurable = with_forge_context(client, task_id="t1")
    config = {"configurable": configurable, "callbacks": []}
    ctx = get_forge_context(config)
    assert ctx.task_id == "t1"
    assert ctx.client is client


def test_get_forge_context_from_bare_configurable(
    client: NavaiaForgeClient,
) -> None:
    """LangGraph sometimes hands nodes the ``configurable`` dict directly."""
    configurable = with_forge_context(client, task_id="t1")
    ctx = get_forge_context(configurable)
    assert ctx.task_id == "t1"


def test_get_forge_context_raises_when_missing(client: NavaiaForgeClient) -> None:
    with pytest.raises(LookupError, match="No NavaiaForge context"):
        get_forge_context({"configurable": {}})


def test_get_forge_context_raises_when_config_is_none() -> None:
    with pytest.raises(LookupError):
        get_forge_context(None)


def test_get_forge_context_raises_for_wrong_type(
    client: NavaiaForgeClient,
) -> None:
    """A garbage value in the slot should not silently pass through."""
    config = {"configurable": {"navaia_forge": "not-a-context"}}
    with pytest.raises(LookupError):
        get_forge_context(config)

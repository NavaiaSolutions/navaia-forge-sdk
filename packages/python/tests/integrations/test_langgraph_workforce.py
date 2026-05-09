"""Tests for the :class:`LangGraphWorkforce` wrapper.

We use a fake graph that captures the ``invoke``/``ainvoke`` arguments so
we can assert the wrapper builds the right ``RunnableConfig`` without
needing a real LangGraph compile.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from navaia_forge import NavaiaForgeClient
from navaia_forge.integrations.langgraph import (
    ForgeContext,
    LangGraphWorkforce,
    get_forge_context,
)


class _FakeGraph:
    """Captures (state, config) on each invoke call. Returns a fixed value."""

    def __init__(self, return_value: Any = None) -> None:
        self.calls: list[tuple[Any, Any]] = []
        self._return_value = return_value if return_value is not None else {"ok": True}

    def invoke(self, state: Any, config: Any = None) -> Any:
        self.calls.append((state, config))
        return self._return_value

    async def ainvoke(self, state: Any, config: Any = None) -> Any:
        self.calls.append((state, config))
        return self._return_value


class _SyncOnlyGraph:
    def invoke(self, state: Any, config: Any = None) -> Any:
        return state


class _AsyncOnlyGraph:
    async def ainvoke(self, state: Any, config: Any = None) -> Any:
        return state


@pytest.fixture
def fake_client() -> Any:
    client = MagicMock(spec=NavaiaForgeClient)
    client.observability = MagicMock()
    return client


def test_rejects_object_without_invoke_or_ainvoke(fake_client: Any) -> None:
    with pytest.raises(TypeError, match="\\.invoke or \\.ainvoke"):
        LangGraphWorkforce(graph=object(), client=fake_client)


def test_run_injects_callback_and_context(fake_client: Any) -> None:
    graph = _FakeGraph()
    wf = LangGraphWorkforce(graph, fake_client, name="my-wf", workforce_id="wf_1")
    wf.run({"q": "hi"}, task_id="task_1")

    assert len(graph.calls) == 1
    state, config = graph.calls[0]
    assert state == {"q": "hi"}
    # Forge context lives on configurable.navaia_forge.
    ctx = get_forge_context(config)
    assert isinstance(ctx, ForgeContext)
    assert ctx.task_id == "task_1"
    assert ctx.workforce_id == "wf_1"
    # Forge callback is appended to the callbacks list.
    callbacks = config["callbacks"]
    assert len(callbacks) == 1
    # Sanity: it's a langchain callback handler.
    assert hasattr(callbacks[0], "on_llm_end")


def test_run_preserves_user_supplied_callbacks(fake_client: Any) -> None:
    user_cb = MagicMock()
    graph = _FakeGraph()
    wf = LangGraphWorkforce(graph, fake_client)
    wf.run({}, task_id="t", config={"callbacks": [user_cb]})

    _, config = graph.calls[0]
    callbacks = config["callbacks"]
    # User callback first, Forge callback appended.
    assert callbacks[0] is user_cb
    assert len(callbacks) == 2


def test_run_preserves_user_configurable_keys(fake_client: Any) -> None:
    graph = _FakeGraph()
    wf = LangGraphWorkforce(graph, fake_client)
    wf.run({}, config={"configurable": {"thread_id": "abc"}})

    _, config = graph.calls[0]
    assert config["configurable"]["thread_id"] == "abc"
    assert "navaia_forge" in config["configurable"]


def test_run_does_not_mutate_user_config(fake_client: Any) -> None:
    user_cfg: dict[str, Any] = {"callbacks": [], "configurable": {"k": "v"}}
    graph = _FakeGraph()
    wf = LangGraphWorkforce(graph, fake_client)
    wf.run({}, config=user_cfg)
    assert user_cfg == {"callbacks": [], "configurable": {"k": "v"}}


def test_run_raises_on_async_only_graph(fake_client: Any) -> None:
    wf = LangGraphWorkforce(_AsyncOnlyGraph(), fake_client)
    with pytest.raises(NotImplementedError, match="\\.arun"):
        wf.run({})


@pytest.mark.asyncio
async def test_arun_invokes_async(fake_client: Any) -> None:
    graph = _FakeGraph(return_value={"async": True})
    wf = LangGraphWorkforce(graph, fake_client)
    result = await wf.arun({"x": 1}, task_id="t1")
    assert result == {"async": True}


@pytest.mark.asyncio
async def test_arun_raises_on_sync_only_graph(fake_client: Any) -> None:
    wf = LangGraphWorkforce(_SyncOnlyGraph(), fake_client)
    with pytest.raises(NotImplementedError, match="\\.run"):
        await wf.arun({})


def test_workforce_exposes_graph_and_name(fake_client: Any) -> None:
    graph = _FakeGraph()
    wf = LangGraphWorkforce(graph, fake_client, name="research")
    assert wf.graph is graph
    assert wf.name == "research"

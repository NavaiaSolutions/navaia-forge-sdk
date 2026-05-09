"""LangGraph ↔ NavaiaForge integration.

Three thin layers, each independently useful:

1. :class:`NavaiaForgeCallback` — a ``langchain_core`` callback handler that
   streams LangGraph chain / LLM / tool events to Forge observability.
2. :class:`ForgeContext` plus :func:`get_forge_context` — inject the Forge
   SDK client and the current task/workforce ids into LangGraph nodes via
   the standard ``RunnableConfig.configurable`` slot.
3. :class:`LangGraphWorkforce` — wrap a compiled graph so it runs as a
   Forge workforce with both of the above pre-wired.

The ``langchain_core`` import is deferred so plain ``import navaia_forge``
still works when the optional extra is not installed::

    pip install "navaia-forge[langgraph]"

Quickstart::

    from langgraph.graph import StateGraph
    from navaia_forge import NavaiaForgeClient
    from navaia_forge.integrations.langgraph import LangGraphWorkforce

    graph = StateGraph(MyState).add_node(...).compile()
    client = NavaiaForgeClient(base_url=..., api_key=...)
    wf = LangGraphWorkforce(graph, client, name="research-team")
    final_state = wf.run({"query": "..."}, task_id="task_123")
"""

from .callback import NavaiaForgeCallback
from .context import ForgeContext, get_forge_context, with_forge_context
from .workforce import LangGraphWorkforce

__all__ = [
    "ForgeContext",
    "LangGraphWorkforce",
    "NavaiaForgeCallback",
    "get_forge_context",
    "with_forge_context",
]

"""
NavaiaForge SDK — LangGraph integration example.

Bring an existing LangGraph workforce into Forge with one line of wiring.
The graph keeps its original shape; the wrapper adds:

- Token-usage and timing telemetry through Forge observability.
- A ``ForgeContext`` injected on ``RunnableConfig.configurable`` so any
  node can call the Forge SDK (knowledge search, tools, conversations,
  etc.) without further setup.

Install:

    pip install "navaia-forge[langgraph]" langgraph langchain-openai

Run:

    NAVAIA_FORGE_BASE_URL=http://localhost:8000 \\
    NAVAIA_FORGE_API_KEY=nf_... \\
    python examples/python/langgraph_workforce.py
"""

from __future__ import annotations

import os
from typing import TypedDict

from langchain_openai import ChatOpenAI  # type: ignore[import-not-found]
from langgraph.graph import END, StateGraph  # type: ignore[import-not-found]

from navaia_forge import NavaiaForgeClient
from navaia_forge.integrations.langgraph import (
    LangGraphWorkforce,
    get_forge_context,
)


class ResearchState(TypedDict, total=False):
    query: str
    knowledge_hits: list[dict]
    answer: str


def search_node(state: ResearchState, config: dict) -> ResearchState:
    """A node that uses the Forge backend through the injected context."""
    forge = get_forge_context(config)
    if forge.workforce_id is None:
        # Local-dev mode without a Forge workforce attached — skip search.
        return {"knowledge_hits": []}
    response = forge.client.knowledge.search(forge.workforce_id, state["query"])
    hits = [r.model_dump() for r in response.results]
    return {"knowledge_hits": hits}


def answer_node(state: ResearchState, config: dict) -> ResearchState:
    """A standard LangGraph LLM call — observability flows automatically."""
    llm = ChatOpenAI(model="gpt-4o-mini")
    context = "\n".join(hit.get("content", "") for hit in state.get("knowledge_hits", []))
    prompt = (
        f"Question: {state['query']}\n\nContext:\n{context}\n\n"
        "Answer concisely using the context."
    )
    result = llm.invoke(prompt)
    return {"answer": str(result.content)}


def build_graph() -> object:
    builder = StateGraph(ResearchState)
    builder.add_node("search", search_node)
    builder.add_node("answer", answer_node)
    builder.set_entry_point("search")
    builder.add_edge("search", "answer")
    builder.add_edge("answer", END)
    return builder.compile()


def main() -> None:
    client = NavaiaForgeClient(
        base_url=os.environ.get("NAVAIA_FORGE_BASE_URL", "http://localhost:8000"),
        api_key=os.environ["NAVAIA_FORGE_API_KEY"],
    )

    # Wrap the compiled graph as a Forge workforce. Optionally bind a
    # workforce_id if the graph should run inside an existing Forge
    # workforce (knowledge search, edges, observability rollups attach
    # to that workforce).
    wf = LangGraphWorkforce(
        graph=build_graph(),
        client=client,
        name="research-team",
        workforce_id=os.environ.get("NAVAIA_FORGE_WORKFORCE_ID"),
        default_model="gpt-4o-mini",
    )

    final = wf.run(
        {"query": "What are NavaiaForge's design goals?"},
        task_id=os.environ.get("NAVAIA_FORGE_TASK_ID"),
    )
    print("Final answer:", final.get("answer"))


if __name__ == "__main__":
    main()

"""Smoke test guarding the public import surface."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_top_level_imports() -> None:
    from navaia_forge import (
        Agent,
        Edge,
        NavaiaForgeClient,
        NavaiaForgeError,
        NavaiaForgeWs,
        Task,
        Workforce,
    )

    # Sanity: each is the right kind of object.
    assert isinstance(NavaiaForgeClient, type)
    assert isinstance(NavaiaForgeWs, type)
    assert issubclass(NavaiaForgeError, Exception)
    for model in (Workforce, Agent, Task, Edge):
        assert hasattr(model, "model_validate")


@pytest.mark.unit
def test_client_resource_namespaces_attached() -> None:
    from navaia_forge import NavaiaForgeClient

    client = NavaiaForgeClient(base_url="http://x", api_key="k")
    for namespace in (
        "workforces",
        "agents",
        "tasks",
        "conversations",
        "knowledge",
        "observability",
        "templates",
        "integrations",
        "tools",
        "setup",
        "auth",
    ):
        assert hasattr(client, namespace), f"client missing {namespace}"
    client.close()

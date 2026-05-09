"""Tests for the NavaiaForge LangChain callback handler.

The pure helpers (``_extract_token_usage``, ``_extract_model_name``) get
unit-tested against synthetic LLMResult-shaped objects. The full
callback integration uses a fake client that records the calls.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from navaia_forge import NavaiaForgeClient
from navaia_forge.integrations.langgraph import NavaiaForgeCallback
from navaia_forge.integrations.langgraph.callback import (
    _extract_model_name,
    _extract_token_usage,
    _name_of,
)

# ── Pure helpers ────────────────────────────────────────────────


def test_extract_token_usage_from_llm_output() -> None:
    response = SimpleNamespace(
        llm_output={
            "token_usage": {"prompt_tokens": 12, "completion_tokens": 34},
            "model_name": "claude-opus-4-6",
        }
    )
    out = _extract_token_usage(response)
    assert out == {"input": 12, "output": 34, "cost_usd": 0.0}


def test_extract_token_usage_from_usage_metadata() -> None:
    """Newer langchain-core surfaces usage on the message itself."""
    message = SimpleNamespace(usage_metadata={"input_tokens": 5, "output_tokens": 7})
    gen = SimpleNamespace(message=message)
    response = SimpleNamespace(generations=[[gen]], llm_output=None)
    out = _extract_token_usage(response)
    assert out["input"] == 5
    assert out["output"] == 7


def test_extract_token_usage_handles_missing_data() -> None:
    response = SimpleNamespace(llm_output=None, generations=[])
    assert _extract_token_usage(response) == {"input": 0, "output": 0, "cost_usd": 0.0}


def test_extract_model_name_returns_none_when_missing() -> None:
    assert _extract_model_name(SimpleNamespace(llm_output=None)) is None


def test_name_of_handles_none() -> None:
    assert _name_of(None) == "<unknown>"


def test_name_of_prefers_explicit_name() -> None:
    assert _name_of({"name": "MyChain", "id": ["x", "y"]}) == "MyChain"


def test_name_of_falls_back_to_id() -> None:
    assert _name_of({"id": ["pkg", "module", "ChatOpenAI"]}) == "ChatOpenAI"


# ── Callback wiring ─────────────────────────────────────────────


@pytest.fixture
def fake_client() -> Any:
    """A NavaiaForgeClient with the ``observability`` resource mocked.

    We never want a real HTTP call from a unit test — and the callback
    only touches ``client.observability.log_token_usage``.
    """
    client = MagicMock(spec=NavaiaForgeClient)
    client.observability = MagicMock()
    return client


def test_callback_logs_token_usage_on_llm_end(fake_client: Any) -> None:
    cb = NavaiaForgeCallback(
        fake_client, task_id="task_1", agent_id="agent_1", default_model="fallback"
    )
    run_id = uuid4()
    cb.on_llm_start({}, ["hello"], run_id=run_id)
    response = SimpleNamespace(
        llm_output={
            "token_usage": {"prompt_tokens": 10, "completion_tokens": 20},
            "model_name": "claude-opus-4-6",
        }
    )
    cb.on_llm_end(response, run_id=run_id)

    fake_client.observability.log_token_usage.assert_called_once()
    kwargs = fake_client.observability.log_token_usage.call_args.kwargs
    assert kwargs["model"] == "claude-opus-4-6"
    assert kwargs["task_id"] == "task_1"
    assert kwargs["agent_id"] == "agent_1"
    assert kwargs["input_tokens"] == 10
    assert kwargs["output_tokens"] == 20
    assert kwargs["duration_ms"] >= 0


def test_callback_uses_default_model_when_response_has_none(fake_client: Any) -> None:
    cb = NavaiaForgeCallback(fake_client, default_model="my-default")
    run_id = uuid4()
    cb.on_llm_start({}, ["x"], run_id=run_id)
    cb.on_llm_end(SimpleNamespace(llm_output=None, generations=[]), run_id=run_id)
    kwargs = fake_client.observability.log_token_usage.call_args.kwargs
    assert kwargs["model"] == "my-default"


def test_callback_swallows_logging_failures(fake_client: Any) -> None:
    """A flaky observability backend must not blow up the user's graph."""
    fake_client.observability.log_token_usage.side_effect = RuntimeError("nope")
    cb = NavaiaForgeCallback(fake_client)
    run_id = uuid4()
    cb.on_llm_start({}, ["x"], run_id=run_id)
    # Should not raise.
    cb.on_llm_end(SimpleNamespace(llm_output=None, generations=[]), run_id=run_id)


def test_callback_chain_lifecycle_does_not_call_observability(
    fake_client: Any,
) -> None:
    """Chain lifecycle is currently log-only; only LLM-end posts usage."""
    cb = NavaiaForgeCallback(fake_client)
    run_id = uuid4()
    cb.on_chain_start({"name": "Plan"}, {"x": 1}, run_id=run_id)
    cb.on_chain_end({"y": 2}, run_id=run_id)
    fake_client.observability.log_token_usage.assert_not_called()


def test_callback_handles_errors_cleanly(fake_client: Any) -> None:
    cb = NavaiaForgeCallback(fake_client)
    run_id = uuid4()
    cb.on_chain_start({}, {}, run_id=run_id)
    cb.on_chain_error(RuntimeError("boom"), run_id=run_id)
    cb.on_tool_start({}, "input", run_id=run_id)
    cb.on_tool_error(RuntimeError("tool boom"), run_id=run_id)
    cb.on_llm_start({}, [], run_id=run_id)
    cb.on_llm_error(RuntimeError("llm boom"), run_id=run_id)
    fake_client.observability.log_token_usage.assert_not_called()

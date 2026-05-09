"""Lazy ``langchain_core`` imports — keep the SDK usable without the extra.

LangGraph users always have ``langchain_core`` installed transitively. We
import the few symbols we need from that package only, never from
``langgraph`` itself, so the integration works even with hand-rolled
graphs as long as they speak the LangChain runnable protocol.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

_INSTALL_HINT = (
    "LangGraph integration requires 'langchain_core'. "
    "Install with: pip install 'navaia-forge[langgraph]'"
)


def require_langchain_core() -> None:
    """Raise a clear error if ``langchain_core`` is not importable."""
    try:
        import langchain_core  # noqa: F401
    except ImportError as exc:  # pragma: no cover — exercised in extras-missing test
        raise ImportError(_INSTALL_HINT) from exc


def import_base_callback_handler() -> Any:
    """Return ``langchain_core.callbacks.BaseCallbackHandler`` or raise."""
    require_langchain_core()
    from langchain_core.callbacks import BaseCallbackHandler

    return BaseCallbackHandler


if TYPE_CHECKING:  # pragma: no cover — type-check only
    from langchain_core.callbacks import BaseCallbackHandler  # noqa: F401
    from langchain_core.runnables import RunnableConfig  # noqa: F401

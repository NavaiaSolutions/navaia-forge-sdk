"""WebSocket client for real-time NavaiaForge events.

Ports the lifecycle, event routing, and reconnection logic of the TypeScript
SDK's ``websocket.ts`` to Python. Uses the synchronous client of the
``websockets`` library (so it works in plain scripts without an event loop).

Typical usage::

    ws = NavaiaForgeWs(config)
    ws.on("task:status", lambda evt: print(evt))
    ws.connect()           # opens the socket (blocking until connected)
    ws.run_forever()       # processes incoming events; returns on disconnect

For users who already manage an event loop, ``poll(timeout=...)`` reads a
single event without blocking forever.
"""

from __future__ import annotations

import contextlib
import json
import threading
import time
from collections.abc import Callable
from typing import Any

try:  # pragma: no cover - optional import path
    from websockets.exceptions import ConnectionClosed
    from websockets.sync.client import ClientConnection
    from websockets.sync.client import connect as ws_connect
except ImportError:  # pragma: no cover - import error surfaced at use-time
    ws_connect = None  # type: ignore[assignment]
    ClientConnection = Any  # type: ignore[assignment, misc]

    class ConnectionClosed(Exception):  # type: ignore[no-redef]  # noqa: N818
        """Stub raised when ``websockets`` is unavailable.

        Name mirrors the upstream ``websockets.exceptions.ConnectionClosed``
        so callers can ``except ConnectionClosed`` regardless of install state.
        """


from .http import HttpConfig

EventName = str
Handler = Callable[..., None]

_TASK_EVENT_TYPES: frozenset[str] = frozenset(
    {"task_created", "task_completed", "task_failed", "task_updated"}
)


def _route_event(event_type: str) -> EventName | None:
    if event_type in _TASK_EVENT_TYPES:
        return "task:status"
    if event_type == "agent_status_changed":
        return "agent:status"
    if event_type == "chat_message":
        return "chat:message"
    if event_type == "system":
        return "system"
    return None


class NavaiaForgeWs:
    """Real-time WebSocket client mirroring the TS SDK lifecycle.

    Supported event names:

    * ``task:status``   — any of ``task_created/completed/failed/updated``
    * ``agent:status``  — agent status change
    * ``chat:message``  — new chat message preview
    * ``system``        — system notification
    * ``message``       — every incoming JSON event (raw)
    * ``open``          — socket opened
    * ``close``         — socket closed (args: code, reason)
    * ``error``         — socket error (args: exception)
    """

    max_reconnect_attempts: int = 10
    reconnect_base_delay: float = 1.0

    def __init__(self, config: HttpConfig) -> None:
        if ws_connect is None:  # pragma: no cover - import-time guard
            raise RuntimeError(
                "The 'websockets' package is required for NavaiaForgeWs. "
                "Install it with: pip install websockets",
            )
        self._config = config
        self._socket: ClientConnection | None = None
        self._listeners: dict[EventName, list[Handler]] = {}
        self._reconnect_attempts = 0
        self._should_reconnect = True
        self._lock = threading.Lock()

    # ── Connection lifecycle ──────────────────────────────────

    @property
    def connected(self) -> bool:
        return self._socket is not None

    def _build_url(self) -> str:
        base = self._config.base_url.rstrip("/")
        # http(s) -> ws(s)
        if base.startswith("https://"):
            base = "wss://" + base[len("https://") :]
        elif base.startswith("http://"):
            base = "ws://" + base[len("http://") :]
        return f"{base}/ws"

    def _build_auth_headers(self) -> list[tuple[str, str]]:
        """Auth headers for the WS upgrade.

        Sent as headers (not URL query) so credentials never appear in
        proxy access logs, browser history, or server-side request logs.
        """
        headers: list[tuple[str, str]] = []
        if self._config.api_key:
            headers.append(("X-API-Key", self._config.api_key))
        return headers

    def connect(self) -> None:
        """Open the WebSocket connection. No-op if already connected."""
        if self._socket is not None:
            return
        self._should_reconnect = True
        url = self._build_url()
        assert ws_connect is not None  # for type checkers
        self._socket = ws_connect(
            url, additional_headers=self._build_auth_headers()
        )
        self._reconnect_attempts = 0
        self._emit("open")

    def disconnect(self) -> None:
        """Close the WebSocket connection and disable reconnection."""
        self._should_reconnect = False
        socket = self._socket
        self._socket = None
        if socket is not None:
            with contextlib.suppress(Exception):
                socket.close(code=1000, reason="Client disconnect")

    # ── Event subscription ────────────────────────────────────

    def on(self, event: EventName, handler: Handler) -> Callable[[], None]:
        """Subscribe to ``event``. Returns an unsubscribe callable."""
        with self._lock:
            self._listeners.setdefault(event, []).append(handler)

        def unsubscribe() -> None:
            with self._lock:
                handlers = self._listeners.get(event)
                if handlers and handler in handlers:
                    handlers.remove(handler)

        return unsubscribe

    def off(self, event: EventName, handler: Handler) -> None:
        with self._lock:
            handlers = self._listeners.get(event)
            if handlers and handler in handlers:
                handlers.remove(handler)

    def remove_all_listeners(self, event: EventName | None = None) -> None:
        with self._lock:
            if event is None:
                self._listeners.clear()
            else:
                self._listeners.pop(event, None)

    # ── Message processing ────────────────────────────────────

    def poll(self, timeout: float | None = None) -> dict[str, Any] | None:
        """Read a single event. Returns ``None`` on timeout or close."""
        socket = self._socket
        if socket is None:
            return None
        try:
            raw = socket.recv(timeout=timeout)
        except TimeoutError:
            return None
        except ConnectionClosed as exc:
            self._handle_close(exc)
            return None
        return self._handle_message(raw)

    def run_forever(self) -> None:
        """Process events until the connection closes (and reconnect attempts fail)."""
        while self._socket is not None:
            try:
                self.poll()
            except Exception as exc:  # pragma: no cover - defensive
                self._emit("error", exc)
                self._handle_close(exc)

    # ── Internals ─────────────────────────────────────────────

    def _handle_message(self, raw: str | bytes) -> dict[str, Any] | None:
        if isinstance(raw, bytes):
            try:
                raw = raw.decode("utf-8")
            except UnicodeDecodeError:
                return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None

        self._emit("message", parsed)
        event_type = parsed.get("type")
        if isinstance(event_type, str):
            channel = _route_event(event_type)
            if channel:
                self._emit(channel, parsed)
        return parsed

    def _handle_close(self, exc: BaseException) -> None:
        socket = self._socket
        self._socket = None
        code = getattr(exc, "code", 1006)
        reason = getattr(exc, "reason", str(exc))
        self._emit("close", code, reason)
        if socket is not None:
            with contextlib.suppress(Exception):
                socket.close()
        self._attempt_reconnect()

    def _attempt_reconnect(self) -> None:
        if not self._should_reconnect:
            return
        if self._reconnect_attempts >= self.max_reconnect_attempts:
            return
        delay = self.reconnect_base_delay * (2 ** self._reconnect_attempts)
        self._reconnect_attempts += 1
        time.sleep(delay)
        try:
            self.connect()
        except Exception as exc:  # pragma: no cover - defensive
            self._emit("error", exc)

    def _emit(self, event: EventName, *args: Any) -> None:
        with self._lock:
            handlers = list(self._listeners.get(event, ()))
        for handler in handlers:
            try:
                handler(*args)
            except Exception:
                # Listener errors must not crash the event loop.
                continue

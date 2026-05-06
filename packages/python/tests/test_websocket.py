"""Tests for the WebSocket client (event routing, listener management).

These tests don't open a real socket — they exercise the message-routing logic
by constructing the client and feeding crafted JSON payloads through the
internal handler.
"""

from __future__ import annotations

import pytest

from navaia_forge import HttpConfig, NavaiaForgeWs


@pytest.fixture
def ws() -> NavaiaForgeWs:
    return NavaiaForgeWs(
        HttpConfig(base_url="http://test.local", api_key="k", timeout=5.0)
    )


@pytest.mark.unit
def test_url_construction_http_to_ws(ws: NavaiaForgeWs) -> None:
    assert ws._build_url() == "ws://test.local/ws?api_key=k"


@pytest.mark.unit
def test_url_construction_https_to_wss() -> None:
    ws = NavaiaForgeWs(
        HttpConfig(base_url="https://forge.navaia.com", api_key="abc", timeout=5.0)
    )
    assert ws._build_url() == "wss://forge.navaia.com/ws?api_key=abc"


@pytest.mark.unit
def test_task_event_routes_to_task_status_channel(ws: NavaiaForgeWs) -> None:
    received: list[dict] = []
    ws.on("task:status", lambda e: received.append(e))
    payload = (
        '{"type": "task_completed", "task_id": "t1", "workforce_id": "w1", '
        '"agent_id": null, "status": "done", "title": "x", '
        '"timestamp": "2026-01-01T00:00:00Z"}'
    )
    parsed = ws._handle_message(payload)
    assert parsed is not None
    assert len(received) == 1
    assert received[0]["task_id"] == "t1"


@pytest.mark.unit
def test_unsubscribe(ws: NavaiaForgeWs) -> None:
    received: list[dict] = []
    unsub = ws.on("message", lambda e: received.append(e))
    unsub()
    ws._handle_message('{"type": "system", "severity": "info", '
                       '"message": "hi", "timestamp": "x"}')
    assert received == []


@pytest.mark.unit
def test_invalid_json_does_not_raise(ws: NavaiaForgeWs) -> None:
    assert ws._handle_message("not-json") is None


@pytest.mark.unit
def test_listener_exception_does_not_break_others(ws: NavaiaForgeWs) -> None:
    received: list[dict] = []
    ws.on("message", lambda _: (_ for _ in ()).throw(RuntimeError("boom")))
    ws.on("message", lambda e: received.append(e))
    ws._handle_message(
        '{"type": "system", "severity": "info", "message": "ok", "timestamp": "x"}'
    )
    assert len(received) == 1

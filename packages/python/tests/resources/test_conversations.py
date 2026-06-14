"""Smoke tests for ConversationsResource.

These mirror the actual backend route shape (verified live):
- POST /conversations            (workforce_id in body)
- GET  /conversations            (workforce_id as query param)
- GET  /conversations/{id}       (returns embedded messages)
- POST /chat/{id}                (returns ChatResponse envelope)
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
def test_list_conversations(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/conversations?workforce_id=wf_1",
        method="GET",
        json={
            "items": [
                {
                    "id": "cv_1",
                    "workforce_id": "wf_1",
                    "title": "Chat",
                }
            ],
            "total": 1,
        },
    )
    convos = client.conversations.list("wf_1")
    assert convos[0].id == "cv_1"


@pytest.mark.integration
def test_create_conversation(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/conversations",
        method="POST",
        json={"id": "cv_2", "workforce_id": "wf_1", "title": "New chat"},
    )
    convo = client.conversations.create("wf_1", title="New chat")
    assert convo.id == "cv_2"
    assert convo.title == "New chat"
    body = httpx_mock.get_requests()[0].read().decode()
    assert "wf_1" in body


@pytest.mark.integration
def test_create_conversation_with_agent(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/conversations",
        method="POST",
        json={
            "id": "cv_3",
            "workforce_id": "wf_1",
            "agent_id": "ag_1",
            "title": "Targeted",
        },
    )
    convo = client.conversations.create("wf_1", title="Targeted", agent_id="ag_1")
    assert convo.id == "cv_3"
    body = httpx_mock.get_requests()[0].read().decode()
    assert "ag_1" in body


@pytest.mark.integration
def test_list_messages_via_detail(httpx_mock, client, base_url) -> None:
    """Backend embeds messages in the conversation detail; SDK pulls them out."""
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/conversations/cv_1",
        method="GET",
        json={
            "id": "cv_1",
            "workforce_id": "wf_1",
            "title": "Chat",
            "messages": [
                {
                    "id": "msg_1",
                    "conversation_id": "cv_1",
                    "role": "assistant",
                    "content": "hi there",
                    "tool_calls": [],
                }
            ],
        },
    )
    messages = client.conversations.messages("cv_1")
    assert messages[0].role == "assistant"
    assert messages[0].content == "hi there"


@pytest.mark.integration
def test_send_message_returns_user_message(httpx_mock, client, base_url) -> None:
    """POST /chat/{id} returns a ChatResponse envelope; SDK surfaces user_message."""
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/chat/cv_1",
        method="POST",
        json={
            "user_message": {
                "id": "msg_1",
                "conversation_id": "cv_1",
                "role": "user",
                "content": "hello",
                "tool_calls": [],
            },
            "assistant_message": None,
            "conversation_id": "cv_1",
        },
    )
    msg = client.conversations.send_message("cv_1", "hello")
    assert msg.content == "hello"
    assert msg.role == "user"


@pytest.mark.integration
def test_send_message_tolerates_null_tool_calls(
    httpx_mock, client, base_url
) -> None:
    """Backend returns ``tool_calls: null`` on chat replies; must not crash."""
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/chat/cv_1",
        method="POST",
        json={
            "user_message": {
                "id": "msg_n",
                "conversation_id": "cv_1",
                "role": "user",
                "content": "hello",
                "tool_calls": None,
                "metadata_json": None,
            },
            "assistant_message": None,
            "conversation_id": "cv_1",
        },
    )
    msg = client.conversations.send_message("cv_1", "hello")
    assert msg.id == "msg_n"
    assert msg.tool_calls == []
    assert msg.metadata_json == {}


@pytest.mark.integration
def test_send_message_falls_back_to_flat_payload(
    httpx_mock, client, base_url
) -> None:
    """If the backend ever returns a flat MessageResponse, parse that too."""
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/chat/cv_1",
        method="POST",
        json={
            "id": "msg_2",
            "conversation_id": "cv_1",
            "role": "user",
            "content": "ping",
            "tool_calls": [],
        },
    )
    msg = client.conversations.send_message("cv_1", "ping")
    assert msg.id == "msg_2"

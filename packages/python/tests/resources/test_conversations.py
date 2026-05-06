"""Smoke tests for ConversationsResource."""

from __future__ import annotations

import pytest


@pytest.mark.integration
def test_list_conversations(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/conversations",
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
def test_send_message(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/conversations/cv_1/messages",
        method="POST",
        json={
            "id": "msg_1",
            "conversation_id": "cv_1",
            "role": "user",
            "content": "hello",
            "agent_id": None,
            "agent_name": None,
            "tool_calls": [],
            "metadata_json": {},
        },
    )
    msg = client.conversations.send_message("cv_1", "hello")
    assert msg.content == "hello"
    assert msg.role == "user"


@pytest.mark.integration
def test_create_conversation(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/workforces/wf_1/conversations",
        method="POST",
        json={"id": "cv_2", "workforce_id": "wf_1", "title": "New chat"},
    )
    convo = client.conversations.create("wf_1", title="New chat")
    assert convo.id == "cv_2"
    assert convo.title == "New chat"


@pytest.mark.integration
def test_list_messages(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/conversations/cv_1/messages",
        method="GET",
        json={
            "items": [
                {
                    "id": "msg_1",
                    "conversation_id": "cv_1",
                    "role": "assistant",
                    "content": "hi there",
                    "agent_id": "ag_1",
                    "agent_name": "Greeter",
                    "tool_calls": [],
                    "metadata_json": {},
                }
            ],
            "total": 1,
        },
    )
    messages = client.conversations.messages("cv_1")
    assert messages[0].role == "assistant"
    assert messages[0].agent_name == "Greeter"


@pytest.mark.integration
def test_send_message_with_agent(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/conversations/cv_1/messages",
        method="POST",
        json={
            "id": "msg_2",
            "conversation_id": "cv_1",
            "role": "user",
            "content": "ping",
            "agent_id": "ag_1",
            "agent_name": None,
            "tool_calls": [],
            "metadata_json": {},
        },
    )
    msg = client.conversations.send_message("cv_1", "ping", agent_id="ag_1")
    assert msg.agent_id == "ag_1"
    body = httpx_mock.get_requests()[0].read().decode()
    assert "ag_1" in body

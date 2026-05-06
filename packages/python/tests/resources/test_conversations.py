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

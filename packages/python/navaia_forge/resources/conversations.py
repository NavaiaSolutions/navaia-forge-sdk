"""Conversation + Message resource."""

from __future__ import annotations

from typing import Any

from ..types import Conversation, Message
from ._base import ResourceBase, parse_list, parse_model


class ConversationsResource(ResourceBase):
    """Operations for conversations and messages."""

    def list(self, workforce_id: str) -> list[Conversation]:
        """List conversations for a workforce."""
        return parse_list(
            Conversation,
            self._http.get_list(f"/workforces/{workforce_id}/conversations"),
        )

    def create(self, workforce_id: str, title: str = "") -> Conversation:
        """Create a new conversation in a workforce."""
        return parse_model(
            Conversation,
            self._http.post(
                f"/workforces/{workforce_id}/conversations",
                {"title": title},
            ),
        )

    def messages(self, conversation_id: str) -> list[Message]:
        """List messages for a conversation."""
        return parse_list(
            Message,
            self._http.get_list(f"/conversations/{conversation_id}/messages"),
        )

    def send_message(
        self,
        conversation_id: str,
        content: str,
        *,
        agent_id: str | None = None,
    ) -> Message:
        """Send a user message to a conversation."""
        body: dict[str, Any] = {
            "conversation_id": conversation_id,
            "content": content,
        }
        if agent_id is not None:
            body["agent_id"] = agent_id
        return parse_model(
            Message,
            self._http.post(f"/conversations/{conversation_id}/messages", body),
        )

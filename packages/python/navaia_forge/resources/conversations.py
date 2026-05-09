"""Conversation + Message resource.

Backend route map (verified against the live OpenAPI):

- ``POST /conversations``           — create, ``workforce_id`` in body
- ``GET  /conversations``           — list, ``workforce_id`` as query param
- ``GET  /conversations/{id}``      — detail, returns the conversation with its
                                       ``messages`` array embedded
- ``POST /chat/{id}``               — send a message; returns the user message
                                       plus an optional assistant message
"""

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
            self._http.get_list("/conversations", params={"workforce_id": workforce_id}),
        )

    def create(
        self,
        workforce_id: str,
        title: str = "",
        *,
        agent_id: str | None = None,
    ) -> Conversation:
        """Create a new conversation in a workforce."""
        body: dict[str, Any] = {"workforce_id": workforce_id, "title": title}
        if agent_id is not None:
            body["agent_id"] = agent_id
        return parse_model(Conversation, self._http.post("/conversations", body))

    def messages(self, conversation_id: str) -> list[Message]:
        """List messages for a conversation.

        The backend exposes messages embedded in the conversation detail
        endpoint (``GET /conversations/{id}``); we pull them out here so
        callers don't have to know that.
        """
        detail = self._http.get(f"/conversations/{conversation_id}")
        if not isinstance(detail, dict):
            return []
        return parse_list(Message, detail.get("messages", []))

    def send_message(
        self,
        conversation_id: str,
        content: str,
        *,
        role: str = "user",
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> Message:
        """Send a message to a conversation and return the user's message.

        The backend's ``POST /chat/{id}`` returns a ``ChatResponse`` envelope
        containing both the user message and an optional assistant reply.
        We surface the user message for symmetry with how the SDK models
        other "create" calls; the assistant reply (if any) is fetched via
        :meth:`messages` once the agent has produced it.
        """
        body: dict[str, Any] = {"content": content, "role": role}
        if tool_calls is not None:
            body["tool_calls"] = list(tool_calls)
        payload = self._http.post(f"/chat/{conversation_id}", body)
        if isinstance(payload, dict) and "user_message" in payload:
            return parse_model(Message, payload["user_message"])
        return parse_model(Message, payload)

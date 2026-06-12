/**
 * Conversation resource — manage conversations and messages.
 *
 * Backend route map (verified against the live OpenAPI):
 *   POST /conversations           — create, workforce_id in body
 *   GET  /conversations           — list, workforce_id as query param
 *   GET  /conversations/{id}      — detail, returns the conversation with its
 *                                    `messages` array embedded
 *   POST /chat/{id}               — send a message; returns the user message
 *                                    plus an optional assistant message
 */

import { get, getList, post } from "../http.js";
import type {
  Conversation,
  Message,
  ResolvedConfig,
} from "../types.js";

export class ConversationResource {
  private readonly config: ResolvedConfig;

  constructor(config: ResolvedConfig) {
    this.config = config;
  }

  /** List conversations for a workforce. */
  list(workforceId: string): Promise<Conversation[]> {
    return getList<Conversation>(this.config, "/conversations", {
      workforce_id: workforceId,
    });
  }

  /** Create a new conversation in a workforce. */
  create(
    workforceId: string,
    title = "",
    agentId?: string,
  ): Promise<Conversation> {
    const body: Record<string, unknown> = {
      workforce_id: workforceId,
      title,
    };
    if (agentId !== undefined) {
      body["agent_id"] = agentId;
    }
    return post<Conversation>(this.config, "/conversations", body);
  }

  /**
   * List messages for a conversation.
   *
   * The backend exposes messages embedded in the conversation detail
   * endpoint (`GET /conversations/{id}`); we pull them out here so callers
   * don't have to know that.
   */
  async messages(conversationId: string): Promise<Message[]> {
    const detail = await get<{ messages?: Message[] }>(
      this.config,
      `/conversations/${conversationId}`,
    );
    return Array.isArray(detail?.messages) ? detail.messages : [];
  }

  /**
   * Send a user message to a conversation and return the user's message.
   *
   * The backend's `POST /chat/{id}` returns a `ChatResponse` envelope
   * containing both the user message and an optional assistant reply. We
   * surface the user message for symmetry with how the SDK models other
   * "create" calls; the assistant reply (if any) is fetched via
   * {@link messages} once the agent has produced it.
   */
  async sendMessage(
    conversationId: string,
    content: string,
    role: "user" | "assistant" | "system" = "user",
  ): Promise<Message> {
    const payload = await post<Message | { user_message?: Message }>(
      this.config,
      `/chat/${conversationId}`,
      { content, role },
    );
    if (
      payload &&
      typeof payload === "object" &&
      "user_message" in payload &&
      payload.user_message
    ) {
      return payload.user_message as Message;
    }
    return payload as Message;
  }
}

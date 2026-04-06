/**
 * Conversation resource — manage conversations and messages.
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
    return getList<Conversation>(
      this.config,
      "/conversations",
      { workforce_id: workforceId },
    );
  }

  /** Get a single conversation by ID. */
  get(conversationId: string): Promise<Conversation> {
    return get<Conversation>(this.config, `/conversations/${conversationId}`);
  }

  /**
   * Create a new conversation.
   *
   * @param workforceId - The workforce to create the conversation in.
   * @param title - Optional title for the conversation.
   */
  create(workforceId: string, title = ""): Promise<Conversation> {
    return post<Conversation>(this.config, "/conversations", {
      workforce_id: workforceId,
      title,
    });
  }

  /** Get all messages in a conversation. */
  messages(conversationId: string): Promise<Message[]> {
    return get<{ messages: Message[] }>(
      this.config,
      `/conversations/${conversationId}`,
    ).then((r) => r.messages ?? []);
  }

  /**
   * Send a message in a conversation.
   *
   * @param conversationId - The conversation to send the message in.
   * @param content - The message content.
   * @param agentId - Optional agent to direct the message to.
   */
  sendMessage(
    conversationId: string,
    content: string,
    agentId?: string,
  ): Promise<Message> {
    const body: Record<string, unknown> = {
      conversation_id: conversationId,
      content,
      role: "user",
    };
    if (agentId) {
      body["agent_id"] = agentId;
    }
    return post<{ user_message: Message }>(
      this.config,
      `/chat/${conversationId}`,
      body,
    ).then((r) => r.user_message);
  }
}

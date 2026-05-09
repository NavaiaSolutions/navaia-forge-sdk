/**
 * Conversation resource — manage conversations and messages.
 */

import { getList, post } from "../http.js";
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
      `/workforces/${workforceId}/conversations`,
    );
  }

  /** Create a new conversation in a workforce. */
  create(workforceId: string, title = ""): Promise<Conversation> {
    return post<Conversation>(
      this.config,
      `/workforces/${workforceId}/conversations`,
      { title },
    );
  }

  /** List messages for a conversation. */
  messages(conversationId: string): Promise<Message[]> {
    return getList<Message>(
      this.config,
      `/conversations/${conversationId}/messages`,
    );
  }

  /**
   * Send a user message to a conversation.
   *
   * @param conversationId - The conversation to post the message in.
   * @param content - The message content.
   * @param agentId - Optional agent to direct the message at.
   */
  sendMessage(
    conversationId: string,
    content: string,
    agentId?: string,
  ): Promise<Message> {
    const body: Record<string, unknown> = {
      conversation_id: conversationId,
      content,
    };
    if (agentId !== undefined) {
      body["agent_id"] = agentId;
    }
    return post<Message>(
      this.config,
      `/conversations/${conversationId}/messages`,
      body,
    );
  }
}

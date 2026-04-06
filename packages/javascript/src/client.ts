/**
 * Main NavaiaForge client — the single entry point for the SDK.
 *
 * @example
 * ```ts
 * import { NavaiaForge } from "@navaia/forge";
 *
 * const nf = new NavaiaForge({ apiKey: "nf_..." });
 *
 * const workforce = await nf.workforces.create({ name: "My Team" });
 * const agent = await nf.agents.create({
 *   workforceId: workforce.id,
 *   name: "Researcher",
 *   role: "research",
 *   instructions: "Find and summarize information.",
 *   modelProvider: "anthropic",
 *   modelName: "sonnet",
 * });
 * ```
 */

import type { NavaiaForgeConfig, ResolvedConfig } from "./types.js";
import { NavaiaForgeWs } from "./websocket.js";
import { AgentResource } from "./resources/agents.js";
import { ConversationResource } from "./resources/conversations.js";
import { IntegrationResource } from "./resources/integrations.js";
import { KnowledgeResource } from "./resources/knowledge.js";
import { ObservabilityResource } from "./resources/observability.js";
import { TaskResource } from "./resources/tasks.js";
import { TemplateResource } from "./resources/templates.js";
import { WorkforceResource } from "./resources/workforces.js";

const DEFAULT_BASE_URL = "http://localhost:8000";
const DEFAULT_TIMEOUT = 60_000;

/**
 * The NavaiaForge SDK client.
 *
 * Provides typed access to all platform resources (workforces, agents, tasks,
 * conversations, knowledge bases, integrations, templates, and observability)
 * plus a WebSocket client for real-time events.
 */
export class NavaiaForge {
  private readonly config: ResolvedConfig;

  /** Workforce CRUD operations. */
  readonly workforces: WorkforceResource;

  /** Agent CRUD operations. */
  readonly agents: AgentResource;

  /** Task lifecycle — create, approve, reject, retry, poll. */
  readonly tasks: TaskResource;

  /** Conversation and chat message management. */
  readonly conversations: ConversationResource;

  /** Knowledge base and document management (RAG). */
  readonly knowledge: KnowledgeResource;

  /** Metrics, token usage, and cost tracking. */
  readonly observability: ObservabilityResource;

  /** Browse and instantiate workforce templates. */
  readonly templates: TemplateResource;

  /** Third-party integration management. */
  readonly integrations: IntegrationResource;

  /** Real-time WebSocket client for task/agent/chat events. */
  readonly ws: NavaiaForgeWs;

  constructor(config: NavaiaForgeConfig) {
    this.config = Object.freeze({
      apiKey: config.apiKey,
      baseUrl: (config.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, ""),
      timeout: config.timeout ?? DEFAULT_TIMEOUT,
    });

    this.workforces = new WorkforceResource(this.config);
    this.agents = new AgentResource(this.config);
    this.tasks = new TaskResource(this.config);
    this.conversations = new ConversationResource(this.config);
    this.knowledge = new KnowledgeResource(this.config);
    this.observability = new ObservabilityResource(this.config);
    this.templates = new TemplateResource(this.config);
    this.integrations = new IntegrationResource(this.config);
    this.ws = new NavaiaForgeWs(this.config);
  }
}

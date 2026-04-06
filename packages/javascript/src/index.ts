/**
 * @navaia/forge — Official TypeScript/JavaScript SDK for the NavaiaForge platform.
 *
 * @example
 * ```ts
 * import { NavaiaForge } from "@navaia/forge";
 *
 * const nf = new NavaiaForge({ apiKey: "nf_..." });
 * const workforce = await nf.workforces.create({ name: "My Team" });
 * ```
 *
 * @packageDocumentation
 */

// ── Main client ────────────────────────────────────────────
export { NavaiaForge } from "./client.js";

// ── Errors ─────────────────────────────────────────────────
export {
  NavaiaForgeError,
  AuthenticationError,
  PermissionError,
  NotFoundError,
  RateLimitError,
  TimeoutError,
} from "./errors.js";

// ── WebSocket ──────────────────────────────────────────────
export { NavaiaForgeWs } from "./websocket.js";
export type { WsEventMap } from "./websocket.js";

// ── Types ──────────────────────────────────────────────────
export type {
  // Config
  NavaiaForgeConfig,
  ResolvedConfig,
  // Workforces
  Workforce,
  WorkforceCreate,
  WorkforceUpdate,
  WorkforceFull,
  Edge,
  // Agents
  Agent,
  AgentCreate,
  AgentUpdate,
  AgentConfig,
  AgentVariable,
  // Tasks
  Task,
  TaskCreate,
  TaskLog,
  WaitForCompletionOptions,
  // Conversations
  Conversation,
  Message,
  MessageCreate,
  ToolCall,
  // Knowledge
  KnowledgeBase,
  KnowledgeBaseCreate,
  KnowledgeDocument,
  // Integrations
  Integration,
  // Observability
  TokenUsage,
  MetricsSummary,
  // Templates
  Template,
  // WebSocket events
  WsEvent,
  WsTaskEvent,
  WsAgentStatusEvent,
  WsChatEvent,
  WsSystemEvent,
  // Enums
  ApprovalMode,
  TaskStatus,
  RuntimeMode,
  AgentStatus,
  ModelProvider,
  KnowledgeSourceType,
  DocumentStatus,
  IntegrationStatus,
  WsEventType,
} from "./types.js";

// ── Resource classes (for advanced usage / extension) ──────
export { WorkforceResource } from "./resources/workforces.js";
export { AgentResource } from "./resources/agents.js";
export { TaskResource } from "./resources/tasks.js";
export { ConversationResource } from "./resources/conversations.js";
export { KnowledgeResource } from "./resources/knowledge.js";
export { ObservabilityResource } from "./resources/observability.js";
export { TemplateResource } from "./resources/templates.js";
export { IntegrationResource } from "./resources/integrations.js";

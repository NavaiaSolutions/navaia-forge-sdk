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
  ValidationError,
  RateLimitError,
  ServerError,
  SyncConflictError,
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
  EdgeCreate,
  EdgeUpdate,
  // Agents
  Agent,
  AgentCreate,
  AgentUpdate,
  AgentConfig,
  AgentMemory,
  AgentVariable,
  WorkforceMember,
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
  KnowledgeBaseUpdate,
  KnowledgeDocument,
  SearchResult,
  SearchResponse,
  WorkforceKnowledgeBaseLink,
  // Tools
  Tool,
  ToolCreate,
  ToolUpdate,
  WorkforceToolLink,
  // Integrations
  Integration,
  AvailablePlugin,
  // Setup
  SetupOptions,
  SetupValidateResult,
  // Observability
  TokenUsage,
  AgentMetrics,
  RLEvaluation,
  AgentCostBreakdown,
  ModelCostBreakdown,
  CostSummary,
  MetricsSummary,
  LogTokenUsageInput,
  // Templates
  Template,
  WorkforceTemplate,
  WorkforceTemplateCreate,
  AgentTemplate,
  AgentTemplateCreate,
  TemplateInstantiateResult,
  // Marketplace
  MarketplaceListing,
  // Auth
  User,
  TokenPair,
  ApiKeyCreated,
  ApiKeyValidation,
  // WebSocket events
  WsEvent,
  WsTaskEvent,
  WsAgentStatusEvent,
  WsChatEvent,
  WsSystemEvent,
  // Sync bundles
  WorkforceSyncBundle,
  SyncWorkforceBundle,
  SyncAgentBundle,
  SyncEdgeBundle,
  SyncTaskBundle,
  SyncTaskLogBundle,
  SyncMessageBundle,
  SyncConversationBundle,
  SyncKnowledgeBaseBundle,
  SyncKnowledgeRepoBundle,
  SyncKnowledgeTextBundle,
  SyncIntegrationBundle,
  SyncEntityCounts,
  SyncImportResult,
  // Pagination
  PaginatedResponse,
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
export { WorkforceResource, EdgesResource } from "./resources/workforces.js";
export { AgentResource } from "./resources/agents.js";
export { TaskResource } from "./resources/tasks.js";
export { ConversationResource } from "./resources/conversations.js";
export { KnowledgeResource } from "./resources/knowledge.js";
export { ObservabilityResource } from "./resources/observability.js";
export { TemplateResource, AgentTemplateResource } from "./resources/templates.js";
export { MarketplaceResource } from "./resources/marketplace.js";
export { IntegrationResource } from "./resources/integrations.js";
export { ToolsResource } from "./resources/tools.js";
export { SetupResource } from "./resources/setup.js";
export { AuthResource } from "./resources/auth.js";
export { SyncResource } from "./resources/sync.js";

// ── HTTP escape hatch ──────────────────────────────────────
export {
  request as httpRequest,
  get as httpGet,
  getList as httpGetList,
  post as httpPost,
  put as httpPut,
  patch as httpPatch,
  del as httpDelete,
  uploadFile as httpUploadFile,
} from "./http.js";

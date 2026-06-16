/**
 * TypeScript type definitions for the NavaiaForge SDK.
 *
 * These mirror the Pydantic schemas from the FastAPI backend and the
 * Python SDK's type definitions.
 */

// ── Enums / Unions ──────────────────────────────────────────

export type ApprovalMode = "auto_run" | "approval_required" | "agent_decides";

export type TaskStatus =
  | "pending"
  | "in_progress"
  | "done"
  | "failed"
  | "blocked"
  | "waiting"
  | "rejected";

/**
 * The two supported runtimes: Claude Code (`claude_max`) and Navaia Code
 * (`navaia_code`). Model execution is delegated to one of these coding-agent
 * CLIs on the backend host.
 */
export type RuntimeMode = "claude_max" | "navaia_code";

export type AgentStatus = "working" | "idle" | "error" | "offline";

export type ModelProvider = "anthropic" | "openai" | "google" | "open_source";

export type KnowledgeSourceType = "upload" | "website" | "integration" | "blank";

export type DocumentStatus = "processing" | "ready" | "failed";

export type IntegrationStatus = "connected" | "disconnected" | "error";

export type WsEventType =
  | "task_created"
  | "task_completed"
  | "task_failed"
  | "task_updated"
  | "agent_status_changed"
  | "workforce_updated"
  | "chat_message"
  | "system";

// ── SDK Configuration ───────────────────────────────────────

export interface NavaiaForgeConfig {
  /** API key for authentication (e.g. "nf_..."). */
  readonly apiKey: string;
  /** Base URL of the NavaiaForge API. Defaults to "http://localhost:8000". */
  readonly baseUrl?: string;
  /** Request timeout in milliseconds. Defaults to 60_000. */
  readonly timeout?: number;
}

/** Resolved (all-required) version of NavaiaForgeConfig. */
export interface ResolvedConfig {
  readonly apiKey: string;
  readonly baseUrl: string;
  readonly timeout: number;
}

// ── Workforces ──────────────────────────────────────────────

export interface Workforce {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  /**
   * Free-form on the backend (`String(50)`); legacy/internal values may appear
   * beyond the two supported {@link RuntimeMode} values, so this response field
   * is a plain string. Use {@link RuntimeMode} when *setting* the mode on
   * create/update.
   */
  readonly runtime_mode: string;
  readonly config_json: Record<string, unknown>;
  readonly status: string;
  readonly created_at: string | null;
  readonly updated_at: string | null;
}

export interface WorkforceCreate {
  readonly name: string;
  readonly description?: string;
  readonly runtime_mode?: RuntimeMode;
  readonly config_json?: Record<string, unknown>;
  readonly template_id?: string;
}

export interface WorkforceUpdate {
  readonly name?: string;
  readonly description?: string;
  readonly runtime_mode?: RuntimeMode;
  readonly config_json?: Record<string, unknown>;
  readonly status?: string;
}

export interface Edge {
  readonly id: string;
  readonly workforce_id: string;
  readonly source_agent_id: string;
  readonly target_agent_id: string;
  readonly approval_mode: ApprovalMode;
  readonly condition_expr: string | null;
  readonly label: string;
  readonly max_runs: number | null;
  readonly task_mode: string;
  readonly created_at: string | null;
}

export interface EdgeCreate {
  readonly workforce_id: string;
  readonly source_agent_id: string;
  readonly target_agent_id: string;
  readonly approval_mode?: ApprovalMode;
  readonly condition_expr?: string;
  readonly label?: string;
  readonly max_runs?: number;
  readonly task_mode?: string;
}

export interface EdgeUpdate {
  readonly approval_mode?: ApprovalMode;
  readonly condition_expr?: string | null;
  readonly label?: string;
  readonly max_runs?: number | null;
  readonly task_mode?: string;
}

export interface WorkforceFull extends Workforce {
  readonly agents: Agent[];
  readonly edges: Edge[];
}

// ── Agents ──────────────────────────────────────────────────

export interface AgentVariable {
  readonly name: string;
  readonly type: "text" | "number" | "boolean" | "json";
  readonly value: string;
}

export interface AgentMemory {
  readonly short_term: boolean;
  readonly long_term: boolean;
}

export interface AgentConfig {
  readonly welcome_message?: string;
  readonly suggest_replies?: boolean;
  readonly timeout?: number;
  readonly task_naming?: string;
  readonly guide?: string;
  readonly parent_prompt?: string;
  readonly data_masking?: boolean;
  readonly autonomy_limit?: number;
  readonly memory?: AgentMemory;
  readonly variables?: AgentVariable[];
}

export interface Agent {
  readonly id: string;
  readonly workforce_id: string;
  readonly name: string;
  readonly role: string;
  readonly instructions: string;
  readonly model_provider: ModelProvider;
  readonly model_name: string;
  readonly escalation_model: string | null;
  readonly max_turns: number;
  readonly tools: Record<string, unknown>[];
  readonly knowledge_bases: string[];
  readonly config_json: Record<string, unknown>;
  readonly position_x: number;
  readonly position_y: number;
  readonly created_at: string | null;
  readonly updated_at: string | null;
}

export interface AgentCreate {
  readonly workforce_id: string;
  readonly name: string;
  readonly role: string;
  readonly instructions: string;
  readonly model_provider?: ModelProvider;
  readonly model_name?: string;
  readonly escalation_model?: string;
  readonly max_turns?: number;
  readonly tools?: Record<string, unknown>[];
  readonly knowledge_bases?: string[];
  readonly config_json?: Record<string, unknown>;
  readonly position_x?: number;
  readonly position_y?: number;
}

export interface AgentUpdate {
  readonly name?: string;
  readonly role?: string;
  readonly instructions?: string;
  readonly model_provider?: ModelProvider;
  readonly model_name?: string;
  readonly escalation_model?: string;
  readonly max_turns?: number;
  readonly tools?: Record<string, unknown>[];
  readonly knowledge_bases?: string[];
  readonly config_json?: Record<string, unknown>;
  readonly position_x?: number;
  readonly position_y?: number;
}

/** An agent attached to a workforce with per-workforce overrides. */
export interface WorkforceMember {
  readonly agent: Agent;
  readonly override_json: Record<string, unknown>;
  readonly position_x: number;
  readonly position_y: number;
}

// ── Tasks ───────────────────────────────────────────────────

export interface Task {
  readonly id: string;
  readonly workforce_id: string;
  readonly agent_id: string | null;
  readonly title: string;
  readonly description: string;
  readonly status: TaskStatus;
  readonly priority: string;
  readonly source: string;
  readonly result: string | null;
  readonly error: string | null;
  readonly retry_count: number;
  readonly metadata_json: Record<string, unknown>;
  readonly created_at: string | null;
  readonly updated_at: string | null;
  readonly started_at: string | null;
  readonly completed_at: string | null;
}

export interface TaskCreate {
  readonly workforce_id: string;
  readonly agent_id?: string;
  readonly title: string;
  readonly description?: string;
  readonly priority?: string;
  readonly metadata_json?: Record<string, unknown>;
}

export interface TaskLog {
  readonly id: string;
  readonly task_id: string;
  readonly event: string;
  readonly detail: string;
  readonly created_at: string | null;
}

export interface WaitForCompletionOptions {
  /** Polling interval in milliseconds. Defaults to 5000. */
  readonly pollInterval?: number;
  /** Maximum time to wait in milliseconds. Defaults to 300_000 (5 minutes). */
  readonly timeout?: number;
}

// ── Conversations ───────────────────────────────────────────

export interface Conversation {
  readonly id: string;
  readonly workforce_id: string;
  readonly title: string;
  readonly created_at: string | null;
  readonly updated_at: string | null;
}

export interface ToolCall {
  readonly id: string;
  readonly tool_name: string;
  readonly input: Record<string, unknown>;
  readonly output: string | null;
  readonly status: "pending" | "success" | "error";
}

export interface Message {
  readonly id: string;
  readonly conversation_id: string;
  readonly role: "user" | "assistant" | "system";
  readonly content: string;
  readonly agent_id: string | null;
  readonly agent_name: string | null;
  readonly tool_calls: ToolCall[];
  readonly metadata_json: Record<string, unknown>;
  readonly created_at: string | null;
}

export interface MessageCreate {
  readonly conversation_id: string;
  readonly content: string;
  readonly agent_id?: string;
}

// ── Knowledge ───────────────────────────────────────────────

export interface KnowledgeBase {
  readonly id: string;
  readonly workforce_id: string;
  readonly name: string;
  readonly description: string;
  readonly source_type: KnowledgeSourceType;
  readonly config_json: Record<string, unknown>;
  readonly document_count: number;
  readonly created_at: string | null;
  readonly updated_at: string | null;
}

export interface KnowledgeBaseCreate {
  readonly name: string;
  readonly description?: string;
  readonly workforce_id?: string;
  readonly source_type?: KnowledgeSourceType;
  readonly retrieval_mode?: string;
  readonly config_json?: Record<string, unknown>;
}

export interface KnowledgeBaseUpdate {
  readonly name?: string;
  readonly description?: string;
  readonly source_type?: KnowledgeSourceType;
  readonly retrieval_mode?: string;
  readonly config_json?: Record<string, unknown>;
}

export interface KnowledgeDocument {
  readonly id: string;
  readonly knowledge_base_id: string;
  readonly filename: string;
  readonly content_type: string;
  readonly size_bytes: number;
  readonly chunk_count: number;
  readonly status: DocumentStatus;
  readonly created_at: string | null;
}

export interface SearchResult {
  readonly content: string;
  readonly score: number;
  readonly document_id: string;
  readonly filename: string;
  readonly chunk_index: number;
  readonly metadata: Record<string, unknown>;
}

export interface SearchResponse {
  readonly results: SearchResult[];
  readonly query: string;
  readonly total: number;
}

export interface WorkforceKnowledgeBaseLink {
  readonly knowledge_base: KnowledgeBase;
  readonly added_at: string | null;
}

// ── Tools ───────────────────────────────────────────────────

export interface Tool {
  readonly id: string;
  readonly owner_id: string | null;
  readonly name: string;
  readonly description: string;
  readonly kind: string;
  readonly icon: string | null;
  readonly integration_id: string | null;
  readonly config_json: Record<string, unknown>;
  readonly is_featured: boolean;
  readonly is_template: boolean;
  readonly created_at: string | null;
  readonly updated_at: string | null;
}

export interface ToolCreate {
  readonly name: string;
  readonly description?: string;
  readonly kind: string;
  readonly icon?: string;
  readonly integration_id?: string;
  readonly config_json?: Record<string, unknown>;
}

export interface ToolUpdate {
  readonly name?: string;
  readonly description?: string;
  readonly kind?: string;
  readonly icon?: string;
  readonly integration_id?: string;
  readonly config_json?: Record<string, unknown>;
}

export interface WorkforceToolLink {
  readonly tool: Tool;
  readonly override_json: Record<string, unknown>;
  readonly added_at: string | null;
}

// ── Integrations ────────────────────────────────────────────

export interface Integration {
  readonly id: string;
  readonly workforce_id: string;
  readonly plugin_name: string;
  readonly display_name: string;
  readonly config_json: Record<string, unknown>;
  readonly status: string;
  readonly last_error: string | null;
  readonly created_at: string | null;
  readonly updated_at: string | null;
}

export interface AvailablePlugin {
  readonly name: string;
  readonly display_name: string;
  readonly description: string;
  readonly version: string;
  readonly active: boolean;
  readonly config_schema: Record<string, unknown>;
}

// ── Setup ──────────────────────────────────────────────────

export interface SetupOptions {
  readonly navaia_cloud_enabled: boolean;
  readonly claude_cli_enabled: boolean;
}

export interface SetupValidateResult {
  readonly status: "healthy" | "unhealthy";
  readonly message: string;
}

// ── Observability ───────────────────────────────────────────

export interface TokenUsage {
  readonly id: string;
  readonly agent_id: string | null;
  readonly task_id: string | null;
  readonly model: string;
  readonly input_tokens: number;
  readonly output_tokens: number;
  readonly total_tokens: number;
  readonly weighted_tokens: number;
  readonly cost_usd: number;
  readonly duration_ms: number;
  readonly date_key: string;
  readonly created_at: string | null;
}

export interface AgentMetrics {
  readonly id: string;
  readonly agent_id: string;
  readonly period: string;
  readonly period_start: string | null;
  readonly tasks_completed: number;
  readonly tasks_failed: number;
  readonly avg_duration_ms: number;
  readonly total_tokens: number;
  readonly total_cost_usd: number;
  readonly quality_score: number;
  readonly created_at: string | null;
}

export interface RLEvaluation {
  readonly id: string;
  readonly agent_id: string;
  readonly batch: number;
  readonly score_delta: number;
  readonly cumulative_score: number;
  readonly quality_rating: number;
  readonly token_efficiency: number;
  readonly summary: string;
  readonly created_at: string | null;
}

export interface AgentCostBreakdown {
  readonly agent_id: string;
  readonly agent_name: string;
  readonly total_tokens: number;
  readonly weighted_tokens: number;
  readonly cost_usd: number;
  readonly call_count: number;
}

export interface ModelCostBreakdown {
  readonly model: string;
  readonly total_tokens: number;
  readonly weighted_tokens: number;
  readonly cost_usd: number;
  readonly call_count: number;
}

export interface CostSummary {
  readonly workforce_id: string;
  readonly period_days: number;
  readonly total_tokens: number;
  readonly total_weighted_tokens: number;
  readonly total_cost_usd: number;
  readonly by_agent: AgentCostBreakdown[];
  readonly by_model: ModelCostBreakdown[];
}

export interface MetricsSummary {
  readonly total_tasks: number;
  readonly completed_tasks: number;
  readonly failed_tasks: number;
  readonly active_agents: number;
  readonly total_tokens_today: number;
  readonly cost_today: number;
  readonly tasks_by_status: Record<string, number>;
  readonly tokens_by_agent: ReadonlyArray<Record<string, unknown>>;
  readonly tokens_by_model: ReadonlyArray<Record<string, unknown>>;
  readonly tasks_over_time: ReadonlyArray<Record<string, unknown>>;
  readonly cost_over_time: ReadonlyArray<Record<string, unknown>>;
}

export interface LogTokenUsageInput {
  readonly model: string;
  readonly agent_id?: string;
  readonly task_id?: string;
  readonly input_tokens?: number;
  readonly output_tokens?: number;
  readonly cost_usd?: number;
  readonly duration_ms?: number;
}

// ── Templates ───────────────────────────────────────────────

export interface WorkforceTemplate {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly category: string;
  readonly runtime_mode: string;
  readonly agents_config: Record<string, unknown>[];
  readonly edges_config: Record<string, unknown>[];
  readonly config_json: Record<string, unknown>;
  readonly is_builtin: boolean;
  readonly price_cents: number;
  readonly is_premium: boolean;
  readonly preview_json: Record<string, unknown>;
  readonly created_at: string | null;
  readonly agent_count?: number;
}

/** Backwards-compatible alias retained for existing imports. */
export type Template = WorkforceTemplate;

export interface WorkforceTemplateCreate {
  readonly name: string;
  readonly description?: string;
  readonly runtime_mode?: string;
  readonly agents_config?: Record<string, unknown>[];
  readonly edges_config?: Record<string, unknown>[];
  readonly config_json?: Record<string, unknown>;
  readonly category?: string;
  readonly price_cents?: number;
  readonly is_premium?: boolean;
  readonly preview_json?: Record<string, unknown>;
}

export interface AgentTemplate {
  readonly id: string;
  readonly name: string;
  readonly role: string;
  readonly description: string;
  readonly instructions: string;
  readonly model_provider: ModelProvider;
  readonly model_name: string;
  readonly escalation_model: string | null;
  readonly max_turns: number;
  readonly tools: Record<string, unknown>[];
  readonly config_json: Record<string, unknown>;
  readonly is_builtin: boolean;
  readonly category: string;
  readonly created_at: string | null;
}

export interface AgentTemplateCreate {
  readonly name: string;
  readonly role: string;
  readonly description?: string;
  readonly instructions?: string;
  readonly model_provider?: ModelProvider;
  readonly model_name?: string;
  readonly escalation_model?: string;
  readonly max_turns?: number;
  readonly tools?: Record<string, unknown>[];
  readonly config_json?: Record<string, unknown>;
  readonly category?: string;
}

export interface TemplateInstantiateResult {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly agents_created: number;
  readonly edges_created: number;
}

// ── Marketplace ────────────────────────────────────────────

/**
 * A published workforce visible in the marketplace catalog.
 *
 * Returned by `GET /marketplace/listings` (browse) and
 * `GET /marketplace/listings/{id}` (detail). Install a listing into your own
 * backend with `client.marketplace.install(listing.id)`.
 */
export interface MarketplaceListing {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly tagline: string | null;
  readonly category: string | null;
  readonly cover_url: string | null;
  readonly price_cents: number;
  readonly currency: string;
  readonly install_count: number;
  readonly published_at: string | null;
  readonly seller_id: string | null;
  readonly seller_name: string | null;
  readonly agent_count: number;
}

// ── Auth ───────────────────────────────────────────────────

export interface User {
  readonly id: string;
  readonly email: string;
  readonly name: string;
  readonly avatar_url: string | null;
  readonly provider: string;
  readonly is_admin: boolean;
  readonly onboarding_completed: boolean;
  readonly created_at: string | null;
}

export interface TokenPair {
  readonly access_token: string;
  readonly refresh_token: string;
  readonly token_type: string;
  readonly user: User;
}

export interface ApiKeyCreated {
  readonly id: string;
  readonly api_key: string;
  readonly name: string;
  readonly last_four: string;
  readonly source: string;
  readonly message: string;
}

export interface ApiKeyValidation {
  readonly valid: boolean;
  readonly user_id: string;
  readonly role: string;
}

// ── WebSocket Events ────────────────────────────────────────

export interface WsTaskEvent {
  readonly type: WsEventType;
  readonly task_id: string;
  readonly workforce_id: string;
  readonly agent_id: string | null;
  readonly status: string;
  readonly title: string;
  readonly timestamp: string;
}

export interface WsAgentStatusEvent {
  readonly type: "agent_status_changed";
  readonly agent_id: string;
  readonly workforce_id: string;
  readonly status: AgentStatus;
  readonly task_id: string | null;
  readonly timestamp: string;
}

export interface WsChatEvent {
  readonly type: "chat_message";
  readonly conversation_id: string;
  readonly message_id: string;
  readonly role: string;
  readonly content_preview: string;
  readonly timestamp: string;
}

export interface WsSystemEvent {
  readonly type: "system";
  readonly severity: "info" | "warning" | "error";
  readonly message: string;
  readonly timestamp: string;
}

export type WsEvent =
  | WsTaskEvent
  | WsAgentStatusEvent
  | WsChatEvent
  | WsSystemEvent;

/** Paginated list response envelope from the API. */
export interface PaginatedResponse<T> {
  readonly items: T[];
  readonly total: number;
}

// ── Sync bundles (two-way local ↔ cloud sync) ───────────────

/** Workforce metadata inside a sync bundle. */
export interface SyncWorkforceBundle {
  readonly origin_id: string;
  readonly name: string;
  readonly description?: string;
  readonly runtime_mode?: string;
  readonly config_json?: Record<string, unknown>;
  readonly status?: string;
}

/** Agent snapshot inside a sync bundle. */
export interface SyncAgentBundle {
  readonly origin_id: string;
  readonly name: string;
  readonly role?: string;
  readonly instructions?: string;
  readonly model_provider?: string;
  readonly model_name?: string;
  readonly escalation_model?: string | null;
  readonly max_turns?: number;
  readonly tools?: ReadonlyArray<Record<string, unknown>>;
  readonly knowledge_bases?: readonly string[];
  readonly config_json?: Record<string, unknown>;
  readonly position_x?: number;
  readonly position_y?: number;
}

/** Edge snapshot inside a sync bundle (references agents by origin_id). */
export interface SyncEdgeBundle {
  readonly origin_id: string;
  readonly source_origin_id: string;
  readonly target_origin_id: string;
  readonly approval_mode?: string;
  readonly label?: string;
  readonly condition_expr?: string | null;
  readonly max_runs?: number | null;
  readonly task_mode?: string | null;
}

/** Task log entry inside a sync bundle. */
export interface SyncTaskLogBundle {
  readonly event: string;
  readonly detail?: string;
  readonly created_at?: string | null;
}

/** Task snapshot inside a sync bundle. */
export interface SyncTaskBundle {
  readonly origin_id: string;
  readonly title: string;
  readonly description?: string;
  readonly status?: string;
  readonly priority?: string;
  readonly result?: string | null;
  readonly error?: string | null;
  readonly metadata_json?: Record<string, unknown>;
  readonly agent_origin_id?: string | null;
  readonly logs?: readonly SyncTaskLogBundle[];
  readonly started_at?: string | null;
  readonly completed_at?: string | null;
  readonly created_at?: string | null;
}

/** Message snapshot inside a sync bundle. */
export interface SyncMessageBundle {
  readonly role: string;
  readonly content: string;
  readonly tool_calls?: ReadonlyArray<Record<string, unknown>>;
  readonly token_count?: number;
  readonly created_at?: string | null;
}

/** Conversation snapshot inside a sync bundle. */
export interface SyncConversationBundle {
  readonly origin_id: string;
  readonly title?: string;
  readonly agent_origin_id?: string | null;
  readonly summary?: string | null;
  readonly messages?: readonly SyncMessageBundle[];
  readonly created_at?: string | null;
}

/** Knowledge repo metadata inside a sync bundle. */
export interface SyncKnowledgeRepoBundle {
  readonly provider?: string;
  readonly owner?: string;
  readonly repo?: string;
  readonly default_branch?: string;
  readonly requires_reauth?: boolean;
}

/** Knowledge text content inside a sync bundle. */
export interface SyncKnowledgeTextBundle {
  readonly title?: string;
  readonly content?: string;
}

/** Knowledge base snapshot inside a sync bundle. */
export interface SyncKnowledgeBaseBundle {
  readonly origin_id: string;
  readonly name: string;
  readonly description?: string;
  readonly repos?: readonly SyncKnowledgeRepoBundle[];
  readonly texts?: readonly SyncKnowledgeTextBundle[];
}

/** Integration snapshot inside a sync bundle (secrets redacted). */
export interface SyncIntegrationBundle {
  readonly origin_id: string;
  readonly plugin_name: string;
  readonly display_name?: string;
  readonly config_json?: Record<string, unknown>;
  readonly redacted_fields?: readonly string[];
  readonly status?: string;
}

/**
 * Complete portable snapshot of a workforce and all its children.
 *
 * Produced by `GET /sync/export/{workforce_id}` and consumed by
 * `POST /sync/import`.
 */
export interface WorkforceSyncBundle {
  readonly bundle_version: string;
  readonly exported_at: string;
  readonly instance_id: string;
  readonly content_hash: string;
  readonly workforce: SyncWorkforceBundle;
  readonly agents: readonly SyncAgentBundle[];
  readonly edges: readonly SyncEdgeBundle[];
  readonly tasks: readonly SyncTaskBundle[];
  readonly conversations: readonly SyncConversationBundle[];
  readonly knowledge_bases: readonly SyncKnowledgeBaseBundle[];
  readonly integrations: readonly SyncIntegrationBundle[];
}

/** Created/updated/deleted counts for one entity type. */
export interface SyncEntityCounts {
  readonly created: number;
  readonly updated: number;
  readonly deleted: number;
}

/** Result of importing a sync bundle. */
export interface SyncImportResult {
  readonly workforce_id: string;
  readonly action: "created" | "updated" | "unchanged";
  readonly agents: SyncEntityCounts;
  readonly edges: SyncEntityCounts;
  readonly knowledge_bases: SyncEntityCounts;
  readonly integrations: SyncEntityCounts;
  readonly tasks_imported: number;
  readonly conversations_imported: number;
  readonly integrations_require_setup: readonly string[];
}

// ── HTTP layer types ────────────────────────────────────────

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface RequestOptions {
  readonly method: HttpMethod;
  readonly path: string;
  readonly body?: unknown;
  readonly params?: Record<string, string>;
  readonly headers?: Record<string, string>;
}

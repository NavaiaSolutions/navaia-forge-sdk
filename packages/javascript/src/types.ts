/**
 * TypeScript type definitions for the NavaiaForge SDK.
 *
 * These mirror the Pydantic schemas from the FastAPI backend and the
 * frontend type definitions.
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

export type RuntimeMode = "claude_max" | "openhands";

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
  readonly runtime_mode: RuntimeMode;
  readonly config_json: Record<string, unknown>;
  readonly status: string;
  readonly created_at: string;
  readonly updated_at: string;
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
  readonly created_at: string;
}

export interface WorkforceFull extends Workforce {
  readonly agents: Agent[];
  readonly edges: Edge[];
}

// ── Agents ──────────────────────────────────────────────────

export interface AgentConfig {
  readonly welcome_message?: string;
  readonly suggest_replies?: boolean;
  readonly timeout?: number;
  readonly task_naming?: string;
  readonly guide?: string;
  readonly parent_prompt?: string;
  readonly data_masking?: boolean;
  readonly autonomy_limit?: number;
  readonly memory?: {
    readonly short_term: boolean;
    readonly long_term: boolean;
  };
  readonly variables?: AgentVariable[];
}

export interface AgentVariable {
  readonly name: string;
  readonly type: "text" | "number" | "boolean" | "json";
  readonly value: string;
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
  readonly config_json: AgentConfig;
  readonly position_x: number;
  readonly position_y: number;
  readonly created_at: string;
  readonly updated_at: string;
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
  readonly config_json?: Partial<AgentConfig>;
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
  readonly config_json?: Partial<AgentConfig>;
  readonly position_x?: number;
  readonly position_y?: number;
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
  readonly created_at: string;
  readonly updated_at: string;
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
  readonly created_at: string;
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
  readonly created_at: string;
  readonly updated_at: string;
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
  readonly created_at: string;
}

export interface ToolCall {
  readonly id: string;
  readonly tool_name: string;
  readonly input: Record<string, unknown>;
  readonly output: string | null;
  readonly status: "pending" | "success" | "error";
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
  readonly created_at: string;
  readonly updated_at: string;
}

export interface KnowledgeBaseCreate {
  readonly workforce_id: string;
  readonly name: string;
  readonly description?: string;
  readonly source_type?: KnowledgeSourceType;
}

export interface KnowledgeDocument {
  readonly id: string;
  readonly knowledge_base_id: string;
  readonly filename: string;
  readonly content_type: string;
  readonly size_bytes: number;
  readonly chunk_count: number;
  readonly status: DocumentStatus;
  readonly created_at: string;
}

// ── Integrations ────────────────────────────────────────────

export interface Integration {
  readonly id: string;
  readonly workforce_id: string;
  readonly name: string;
  readonly type: string;
  readonly category: string;
  readonly status: IntegrationStatus;
  readonly config_json: Record<string, unknown>;
  readonly icon_url: string | null;
  readonly created_at: string;
  readonly updated_at: string;
}

// ── Observability ───────────────────────────────────────────

export interface TokenUsage {
  readonly id: string;
  readonly agent_id: string;
  readonly task_id: string | null;
  readonly model: string;
  readonly input_tokens: number;
  readonly output_tokens: number;
  readonly cost_weighted: number;
  readonly created_at: string;
}

export interface MetricsSummary {
  readonly total_tasks: number;
  readonly completed_tasks: number;
  readonly failed_tasks: number;
  readonly active_agents: number;
  readonly total_tokens_today: number;
  readonly cost_today: number;
  readonly tasks_by_status: Record<TaskStatus, number>;
  readonly tokens_by_agent: ReadonlyArray<{
    agent_id: string;
    agent_name: string;
    tokens: number;
  }>;
  readonly tokens_by_model: ReadonlyArray<{
    model: string;
    tokens: number;
  }>;
  readonly tasks_over_time: ReadonlyArray<{
    date: string;
    count: number;
  }>;
  readonly cost_over_time: ReadonlyArray<{
    date: string;
    cost: number;
  }>;
}

// ── Templates ───────────────────────────────────────────────

export interface Template {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly category: string;
  readonly runtime_mode: string;
  readonly agents_config: Record<string, unknown>[];
  readonly edges_config: Record<string, unknown>[];
  readonly config_json: Record<string, unknown>;
  readonly is_builtin: boolean;
  readonly created_at: string;
  readonly agent_count?: number;
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

// ── HTTP layer types ────────────────────────────────────────

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface RequestOptions {
  readonly method: HttpMethod;
  readonly path: string;
  readonly body?: unknown;
  readonly params?: Record<string, string>;
  readonly headers?: Record<string, string>;
}

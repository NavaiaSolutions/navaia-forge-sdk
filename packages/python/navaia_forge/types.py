"""Pydantic v2 models for the NavaiaForge SDK.

These mirror the FastAPI backend's Pydantic schemas and the TypeScript SDK's
type definitions. Field names use the exact wire format (snake_case) so the
models round-trip cleanly with the API.

Models are deliberately permissive (extra fields ignored) so that minor backend
schema additions do not break older SDK versions.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ── Type aliases (string literal unions) ────────────────────────

ApprovalMode = Literal["auto_run", "approval_required", "agent_decides"]
TaskStatus = Literal[
    "pending",
    "queued",
    "in_progress",
    "waiting_question",
    "waiting_plan",
    "waiting_blocked",
    "done",
    "failed",
    "cancelled",
]
RuntimeMode = Literal["claude_max", "openhands", "genexa_code", "claw_code", "navaia_forge"]
AgentStatus = Literal["working", "idle", "error", "offline"]
ModelProvider = Literal[
    "anthropic",
    "openai",
    "google",
    "open_source",
    "openrouter",
    "claude_max",
    "claw_code",
    "navaia_forge",
    "genexa_code",
]
KnowledgeSourceType = Literal["upload", "website", "integration", "blank"]
DocumentStatus = Literal["processing", "ready", "failed"]
IntegrationStatus = Literal["connected", "disconnected", "error"]
WsEventType = Literal[
    "task_created",
    "task_completed",
    "task_failed",
    "task_updated",
    "agent_status_changed",
    "workforce_updated",
    "chat_message",
    "system",
]


class _Base(BaseModel):
    """Shared base model — permissive extras, populate by name."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
        # Allow round-tripping unknown enum values (e.g. new statuses) as strings.
        use_enum_values=True,
    )


# ── Workforces ──────────────────────────────────────────────────


class Workforce(_Base):
    id: str
    name: str
    description: str = ""
    runtime_mode: RuntimeMode = "claude_max"
    config_json: dict[str, Any] = Field(default_factory=dict)
    status: str = ""
    # Marketplace fields — populated after publish().
    is_public: bool = False
    moderation_status: str | None = None
    published_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class WorkforceCreate(_Base):
    name: str
    description: str = ""
    runtime_mode: RuntimeMode = "claude_max"
    config_json: dict[str, Any] | None = None
    template_id: str | None = None


class WorkforceUpdate(_Base):
    name: str | None = None
    description: str | None = None
    runtime_mode: RuntimeMode | None = None
    config_json: dict[str, Any] | None = None
    status: str | None = None


class Edge(_Base):
    id: str
    workforce_id: str
    source_agent_id: str
    target_agent_id: str
    approval_mode: ApprovalMode = "agent_decides"
    condition_expr: str | None = None
    label: str = ""
    max_runs: int | None = None
    task_mode: str = ""
    created_at: str | None = None


# ── Agents ──────────────────────────────────────────────────────


class AgentVariable(_Base):
    name: str
    type: Literal["text", "number", "boolean", "json"]
    value: str


class AgentMemory(_Base):
    short_term: bool = False
    long_term: bool = False


class AgentConfig(_Base):
    welcome_message: str | None = None
    suggest_replies: bool | None = None
    timeout: int | None = None
    task_naming: str | None = None
    guide: str | None = None
    parent_prompt: str | None = None
    data_masking: bool | None = None
    autonomy_limit: int | None = None
    memory: AgentMemory | None = None
    variables: list[AgentVariable] | None = None


class Agent(_Base):
    id: str
    workforce_id: str
    name: str
    role: str = ""
    instructions: str = ""
    model_provider: ModelProvider = "anthropic"
    model_name: str = "sonnet"
    escalation_model: str | None = None
    max_turns: int = 25
    tools: list[dict[str, Any]] = Field(default_factory=list)
    knowledge_bases: list[str] = Field(default_factory=list)
    config_json: dict[str, Any] = Field(default_factory=dict)
    position_x: float = 0
    position_y: float = 0
    created_at: str | None = None
    updated_at: str | None = None


class AgentCreate(_Base):
    workforce_id: str
    name: str
    role: str
    instructions: str
    model_provider: ModelProvider = "anthropic"
    model_name: str = "sonnet"
    escalation_model: str | None = None
    max_turns: int = 25
    tools: list[dict[str, Any]] | None = None
    knowledge_bases: list[str] | None = None
    config_json: dict[str, Any] | None = None
    position_x: float = 0
    position_y: float = 0


class WorkforceMember(_Base):
    """An agent attached to a workforce with per-workforce overrides."""

    agent: Agent
    override_json: dict[str, Any] = Field(default_factory=dict)
    position_x: float = 0.0
    position_y: float = 0.0


class AgentUpdate(_Base):
    name: str | None = None
    role: str | None = None
    instructions: str | None = None
    model_provider: ModelProvider | None = None
    model_name: str | None = None
    escalation_model: str | None = None
    max_turns: int | None = None
    tools: list[dict[str, Any]] | None = None
    knowledge_bases: list[str] | None = None
    config_json: dict[str, Any] | None = None
    position_x: float | None = None
    position_y: float | None = None


# ── Tasks ───────────────────────────────────────────────────────


class Task(_Base):
    id: str
    workforce_id: str
    agent_id: str | None = None
    title: str
    description: str = ""
    status: TaskStatus = "pending"
    priority: str = "standard"
    source: str = ""
    result: str | None = None
    error: str | None = None
    retry_count: int = 0
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class TaskCreate(_Base):
    workforce_id: str
    agent_id: str | None = None
    title: str
    description: str = ""
    priority: str = "standard"
    metadata_json: dict[str, Any] | None = None


class TaskLog(_Base):
    id: str
    task_id: str
    event: str
    detail: str = ""
    created_at: str | None = None


# ── Conversations & Messages ────────────────────────────────────


class Conversation(_Base):
    id: str
    workforce_id: str
    title: str = ""
    created_at: str | None = None
    updated_at: str | None = None


class ToolCall(_Base):
    id: str
    tool_name: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: str | None = None
    status: Literal["pending", "success", "error"] = "pending"


class Message(_Base):
    id: str
    conversation_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    agent_id: str | None = None
    agent_name: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


# ── Knowledge ───────────────────────────────────────────────────


class KnowledgeBase(_Base):
    id: str
    # Library KBs (not yet attached to a workforce) come back with
    # workforce_id=null; only workforce-scoped KBs carry a value.
    workforce_id: str | None = None
    name: str
    description: str = ""
    source_type: KnowledgeSourceType = "upload"
    config_json: dict[str, Any] = Field(default_factory=dict)
    document_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class KnowledgeDocument(_Base):
    id: str
    knowledge_base_id: str
    filename: str
    content_type: str = ""
    size_bytes: int = 0
    chunk_count: int = 0
    status: DocumentStatus = "processing"
    created_at: str | None = None


class SearchResult(_Base):
    """A single retrieved chunk from a knowledge-base search."""

    content: str
    score: float
    document_id: str
    filename: str = ""
    chunk_index: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(_Base):
    """Envelope for ``POST /knowledge-bases/{kb_id}/search``."""

    results: list[SearchResult] = Field(default_factory=list)
    query: str = ""
    total: int = 0


class WorkforceKnowledgeBaseLink(_Base):
    """Attachment record returned when adding a KB to a workforce."""

    knowledge_base: KnowledgeBase
    added_at: str | None = None


# ── Tools ───────────────────────────────────────────────────────


class Tool(_Base):
    """A reusable tool definition (registered with the platform)."""

    id: str
    owner_id: str | None = None
    name: str
    description: str = ""
    kind: str
    icon: str | None = None
    integration_id: str | None = None
    config_json: dict[str, Any] = Field(default_factory=dict)
    is_featured: bool = False
    is_template: bool = False
    created_at: str | None = None
    updated_at: str | None = None


class ToolCreate(_Base):
    name: str
    description: str = ""
    kind: str
    icon: str | None = None
    integration_id: str | None = None
    config_json: dict[str, Any] | None = None


class ToolUpdate(_Base):
    name: str | None = None
    description: str | None = None
    kind: str | None = None
    icon: str | None = None
    integration_id: str | None = None
    config_json: dict[str, Any] | None = None


class WorkforceToolLink(_Base):
    """Attachment record when adding a tool to a workforce."""

    tool: Tool
    override_json: dict[str, Any] = Field(default_factory=dict)
    added_at: str | None = None


# ── Integrations ────────────────────────────────────────────────


class Integration(_Base):
    """An installed integration plugin tied to a workforce."""

    id: str
    workforce_id: str
    plugin_name: str
    display_name: str = ""
    config_json: dict[str, Any] = Field(default_factory=dict)
    status: str = "inactive"
    last_error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AvailablePlugin(_Base):
    """A registered integration plugin available to install."""

    name: str
    display_name: str = ""
    description: str = ""
    version: str = ""
    active: bool = False
    config_schema: dict[str, Any] = Field(default_factory=dict)


class SetupOptions(_Base):
    """Which onboarding paths are enabled in the deployment."""

    navaia_cloud_enabled: bool = False
    claude_cli_enabled: bool = False


class SetupValidateResult(_Base):
    """Result of ``POST /setup/validate``."""

    status: Literal["healthy", "unhealthy"]
    message: str = ""


# ── Observability ───────────────────────────────────────────────


class TokenUsage(_Base):
    """Single token-usage event logged via ``POST /token-usage``."""

    id: str
    agent_id: str | None = None
    task_id: str | None = None
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    weighted_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    date_key: str = ""
    created_at: str | None = None


class AgentMetrics(_Base):
    """Per-agent rolled-up metrics row."""

    id: str
    agent_id: str
    period: str = "daily"
    period_start: str | None = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    avg_duration_ms: float = 0.0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    quality_score: float = 0.0
    created_at: str | None = None


class RLEvaluation(_Base):
    """Reinforcement-learning evaluation entry for an agent."""

    id: str
    agent_id: str
    batch: int = 0
    score_delta: float = 0.0
    cumulative_score: float = 0.0
    quality_rating: int = 0
    token_efficiency: float = 0.0
    summary: str = ""
    created_at: str | None = None


class AgentCostBreakdown(_Base):
    agent_id: str
    agent_name: str = ""
    total_tokens: int = 0
    weighted_tokens: int = 0
    cost_usd: float = 0.0
    call_count: int = 0


class ModelCostBreakdown(_Base):
    model: str
    total_tokens: int = 0
    weighted_tokens: int = 0
    cost_usd: float = 0.0
    call_count: int = 0


class CostSummary(_Base):
    """Cost rollup returned by ``GET /workforces/{id}/cost``."""

    workforce_id: str
    period_days: int = 30
    total_tokens: int = 0
    total_weighted_tokens: int = 0
    total_cost_usd: float = 0.0
    by_agent: list[AgentCostBreakdown] = Field(default_factory=list)
    by_model: list[ModelCostBreakdown] = Field(default_factory=list)


class MetricsSummary(_Base):
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    active_agents: int = 0
    total_tokens_today: int = 0
    cost_today: float = 0
    tasks_by_status: dict[str, int] = Field(default_factory=dict)
    tokens_by_agent: list[dict[str, Any]] = Field(default_factory=list)
    tokens_by_model: list[dict[str, Any]] = Field(default_factory=list)
    tasks_over_time: list[dict[str, Any]] = Field(default_factory=list)
    cost_over_time: list[dict[str, Any]] = Field(default_factory=list)


# ── Templates ───────────────────────────────────────────────────


class WorkforceTemplate(_Base):
    """Pre-baked workforce blueprint exposed via ``/workforce-templates``."""

    id: str
    name: str
    description: str = ""
    category: str = ""
    runtime_mode: str = ""
    agents_config: list[dict[str, Any]] = Field(default_factory=list)
    edges_config: list[dict[str, Any]] = Field(default_factory=list)
    config_json: dict[str, Any] = Field(default_factory=dict)
    is_builtin: bool = False
    price_cents: int = 0
    is_premium: bool = False
    preview_json: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    agent_count: int | None = None


# Alias retained for backward-compatible imports (``from navaia_forge import Template``).
Template = WorkforceTemplate


class WorkforceTemplateCreate(_Base):
    name: str
    description: str = ""
    runtime_mode: str = "claude_max"
    agents_config: list[dict[str, Any]] | None = None
    edges_config: list[dict[str, Any]] | None = None
    config_json: dict[str, Any] | None = None
    category: str = "general"
    price_cents: int = 0
    is_premium: bool = False
    preview_json: dict[str, Any] | None = None


class AgentTemplate(_Base):
    """Reusable agent blueprint exposed via ``/agent-templates``."""

    id: str
    name: str
    role: str
    description: str = ""
    instructions: str = ""
    model_provider: ModelProvider = "anthropic"
    model_name: str = "sonnet"
    escalation_model: str | None = None
    max_turns: int = 25
    tools: list[dict[str, Any]] = Field(default_factory=list)
    config_json: dict[str, Any] = Field(default_factory=dict)
    is_builtin: bool = False
    category: str = "general"
    created_at: str | None = None


class AgentTemplateCreate(_Base):
    name: str
    role: str
    description: str = ""
    instructions: str = ""
    model_provider: ModelProvider = "anthropic"
    model_name: str = "sonnet"
    escalation_model: str | None = None
    max_turns: int = 25
    tools: list[dict[str, Any]] | None = None
    config_json: dict[str, Any] | None = None
    category: str = "general"


class TemplateInstantiateResult(_Base):
    """Lightweight result returned by ``POST /workforce-templates/{id}/instantiate``."""

    id: str
    name: str
    description: str = ""
    agents_created: int = 0
    edges_created: int = 0


# ── Auth ────────────────────────────────────────────────────────


class User(_Base):
    """Authenticated user profile (``GET /auth/me``)."""

    id: str
    email: str
    name: str
    avatar_url: str | None = None
    provider: str = ""
    is_admin: bool = False
    onboarding_completed: bool = False
    created_at: str | None = None


class TokenPair(_Base):
    """JWT access/refresh pair returned by login/register/refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: User


class ApiKeyCreated(_Base):
    """Result of ``POST /auth/keys`` — the plaintext key shown only once."""

    api_key: str
    key_hash: str
    name: str = ""
    message: str = ""


class ApiKeyValidation(_Base):
    """Result of ``GET /auth/validate``."""

    valid: bool
    user_id: str
    role: str = ""


# ── Composite (workforce + agents + edges) ──────────────────────


class WorkforceFull(Workforce):
    agents: list[Agent] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)


# ── WebSocket events ────────────────────────────────────────────


class WsTaskEvent(_Base):
    type: WsEventType
    task_id: str
    workforce_id: str
    agent_id: str | None = None
    status: str
    title: str = ""
    timestamp: str


class WsAgentStatusEvent(_Base):
    type: Literal["agent_status_changed"]
    agent_id: str
    workforce_id: str
    status: AgentStatus
    task_id: str | None = None
    timestamp: str


class WsChatEvent(_Base):
    type: Literal["chat_message"]
    conversation_id: str
    message_id: str
    role: str
    content_preview: str = ""
    timestamp: str


class WsSystemEvent(_Base):
    type: Literal["system"]
    severity: Literal["info", "warning", "error"] = "info"
    message: str
    timestamp: str


WsEvent = WsTaskEvent | WsAgentStatusEvent | WsChatEvent | WsSystemEvent


# ── Pagination ──────────────────────────────────────────────────


class PaginatedResponse(_Base):
    """Generic paginated envelope: ``{"items": [...], "total": N}``."""

    items: list[Any] = Field(default_factory=list)
    total: int = 0

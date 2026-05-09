/**
 * Observability resource — metrics, evaluations, token-usage logging, cost.
 */

import { get, getList, post, request } from "../http.js";
import type {
  AgentMetrics,
  CostSummary,
  LogTokenUsageInput,
  MetricsSummary,
  ResolvedConfig,
  RLEvaluation,
  TokenUsage,
} from "../types.js";

export class ObservabilityResource {
  private readonly config: ResolvedConfig;

  constructor(config: ResolvedConfig) {
    this.config = config;
  }

  // ── Workforce-level ──────────────────────────────────────

  /**
   * Fetch the freeform dashboard summary for a workforce.
   *
   * The backend response shape is intentionally flexible (task counts,
   * token rollups, etc.) and may evolve.
   */
  async summary(workforceId: string): Promise<MetricsSummary> {
    const result = await request<MetricsSummary | null>(
      this.config,
      "GET",
      `/workforces/${workforceId}/metrics`,
    );
    return (result ?? {}) as MetricsSummary;
  }

  /** Fetch the cost breakdown for a workforce over `days` days. */
  cost(workforceId: string, days = 30): Promise<CostSummary> {
    return get<CostSummary>(
      this.config,
      `/workforces/${workforceId}/cost`,
      { days: String(days) },
    );
  }

  /**
   * Get token usage history for a workforce.
   *
   * @param workforceId - The workforce to query.
   * @param days - Number of days of history to return. Defaults to 7.
   */
  tokenUsage(workforceId: string, days = 7): Promise<TokenUsage[]> {
    return get<TokenUsage[]>(
      this.config,
      `/workforces/${workforceId}/metrics/tokens`,
      { days: String(days) },
    );
  }

  // ── Agent-level ──────────────────────────────────────────

  /** Fetch rolled-up metrics rows for an agent. */
  agentMetrics(
    agentId: string,
    options: { period?: string; limit?: number } = {},
  ): Promise<AgentMetrics[]> {
    return getList<AgentMetrics>(
      this.config,
      `/agents/${agentId}/metrics`,
      {
        period: options.period ?? "daily",
        limit: String(options.limit ?? 30),
      },
    );
  }

  /** Fetch RL evaluations for an agent. */
  agentEvaluations(agentId: string, limit = 20): Promise<RLEvaluation[]> {
    return getList<RLEvaluation>(
      this.config,
      `/agents/${agentId}/evaluations`,
      { limit: String(limit) },
    );
  }

  // ── Token usage ──────────────────────────────────────────

  /** Log a single token-usage event. */
  logTokenUsage(input: LogTokenUsageInput): Promise<TokenUsage> {
    const body: Record<string, unknown> = {
      model: input.model,
      input_tokens: input.input_tokens ?? 0,
      output_tokens: input.output_tokens ?? 0,
      cost_usd: input.cost_usd ?? 0,
      duration_ms: input.duration_ms ?? 0,
    };
    if (input.agent_id !== undefined) {
      body["agent_id"] = input.agent_id;
    }
    if (input.task_id !== undefined) {
      body["task_id"] = input.task_id;
    }
    return post<TokenUsage>(this.config, "/token-usage", body);
  }
}

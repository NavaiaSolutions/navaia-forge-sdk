/**
 * Observability resource — metrics and token usage.
 */

import { get } from "../http.js";
import type {
  MetricsSummary,
  ResolvedConfig,
  TokenUsage,
} from "../types.js";

export class ObservabilityResource {
  private readonly config: ResolvedConfig;

  constructor(config: ResolvedConfig) {
    this.config = config;
  }

  /** Get a metrics summary for a workforce. */
  summary(workforceId: string): Promise<MetricsSummary> {
    return get<MetricsSummary>(
      this.config,
      `/workforces/${workforceId}/metrics`,
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
}

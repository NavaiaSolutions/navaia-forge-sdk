/**
 * Integration resource — manage third-party integrations.
 */

import { del, get, getList, put } from "../http.js";
import type { Integration, ResolvedConfig } from "../types.js";

export class IntegrationResource {
  private readonly config: ResolvedConfig;

  constructor(config: ResolvedConfig) {
    this.config = config;
  }

  /**
   * List integrations, optionally filtered by workforce.
   *
   * @param workforceId - If provided, only integrations for this workforce are returned.
   */
  list(workforceId?: string): Promise<Integration[]> {
    const params = workforceId
      ? { workforce_id: workforceId }
      : undefined;
    return getList<Integration>(this.config, "/integrations", params);
  }

  /** Get a single integration by ID. */
  get(integrationId: string): Promise<Integration> {
    return get<Integration>(this.config, `/integrations/${integrationId}`);
  }

  /**
   * Update the configuration for an integration.
   *
   * @param integrationId - The integration to configure.
   * @param configJson - Configuration key-value pairs.
   */
  configure(
    integrationId: string,
    configJson: Record<string, unknown>,
  ): Promise<Integration> {
    return put<Integration>(this.config, `/integrations/${integrationId}`, {
      config_json: configJson,
    });
  }

  /** Disconnect (delete) an integration. */
  disconnect(integrationId: string): Promise<void> {
    return del<void>(this.config, `/integrations/${integrationId}`);
  }
}

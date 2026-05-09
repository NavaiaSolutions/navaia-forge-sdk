/**
 * Integrations resource — installable plugins (Slack, GitHub, Linear, ...) plus CRUD.
 */

import { del, get, getList, post, put } from "../http.js";
import type {
  AvailablePlugin,
  Integration,
  ResolvedConfig,
} from "../types.js";

export class IntegrationResource {
  private readonly config: ResolvedConfig;

  constructor(config: ResolvedConfig) {
    this.config = config;
  }

  // ── Plugin registry ──────────────────────────────────────

  /** List all integration plugins registered on the server. */
  listPlugins(): Promise<AvailablePlugin[]> {
    return get<AvailablePlugin[]>(this.config, "/plugins");
  }

  // ── Integrations CRUD ────────────────────────────────────

  /** List integrations, optionally scoped to a workforce. */
  list(
    options: { workforceId?: string; offset?: number; limit?: number } = {},
  ): Promise<Integration[]> {
    const params: Record<string, string> = {
      offset: String(options.offset ?? 0),
      limit: String(options.limit ?? 50),
    };
    if (options.workforceId !== undefined) {
      params["workforce_id"] = options.workforceId;
    }
    return getList<Integration>(this.config, "/integrations", params);
  }

  /**
   * Fetch a single integration by ID.
   *
   * The backend does not expose a single-integration GET endpoint; this
   * helper round-trips through {@link list} and filters client-side.
   */
  async get(integrationId: string): Promise<Integration> {
    const all = await this.list();
    const match = all.find((item) => item.id === integrationId);
    if (!match) {
      throw new Error(`Integration ${integrationId} not found`);
    }
    return match;
  }

  /** Install and activate a plugin against a workforce. */
  create(input: {
    workforce_id: string;
    plugin_name: string;
    display_name?: string;
    config_json?: Record<string, unknown>;
  }): Promise<Integration> {
    return post<Integration>(this.config, "/integrations", {
      workforce_id: input.workforce_id,
      plugin_name: input.plugin_name,
      display_name: input.display_name ?? "",
      config_json: input.config_json ?? {},
    });
  }

  /** Update an integration's display name, config, or status. */
  update(
    integrationId: string,
    input: {
      display_name?: string;
      config_json?: Record<string, unknown>;
      status?: string;
    },
  ): Promise<Integration> {
    return put<Integration>(
      this.config,
      `/integrations/${integrationId}`,
      input,
    );
  }

  /**
   * Configure an integration — updates `config_json` only.
   * Convenience around {@link update}.
   */
  configure(
    integrationId: string,
    configJson: Record<string, unknown>,
  ): Promise<Integration> {
    return this.update(integrationId, { config_json: configJson });
  }

  /** Uninstall an integration (deactivates the plugin). */
  delete(integrationId: string): Promise<void> {
    return del<void>(this.config, `/integrations/${integrationId}`);
  }

  /** Backwards-compatible alias for {@link delete}. */
  disconnect(integrationId: string): Promise<void> {
    return this.delete(integrationId);
  }
}

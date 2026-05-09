/**
 * Template resources.
 *
 * The backend exposes two distinct template families under `/api/v1`:
 *
 * - `/workforce-templates` — pre-baked multi-agent workforces with edges.
 * - `/agent-templates`     — reusable single-agent blueprints.
 *
 * The top-level {@link TemplateResource} mirrors the workforce-template
 * endpoints (preserving the legacy `client.templates.list()` shape) and
 * exposes a nested {@link AgentTemplateResource} via `templates.agents`.
 */

import { del, get, getList, post } from "../http.js";
import type {
  AgentTemplate,
  AgentTemplateCreate,
  ResolvedConfig,
  TemplateInstantiateResult,
  WorkforceTemplate,
  WorkforceTemplateCreate,
} from "../types.js";

function dropUndefined(
  payload: Record<string, unknown>,
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(payload)) {
    if (value !== undefined && value !== null) {
      out[key] = String(value);
    }
  }
  return out;
}

/** Operations against `/api/v1/agent-templates`. */
export class AgentTemplateResource {
  private readonly config: ResolvedConfig;

  constructor(config: ResolvedConfig) {
    this.config = config;
  }

  /** List agent templates, optionally filtered by `category`. */
  list(
    options: { category?: string; offset?: number; limit?: number } = {},
  ): Promise<AgentTemplate[]> {
    const params = dropUndefined({
      category: options.category,
      offset: options.offset ?? 0,
      limit: options.limit ?? 50,
    });
    return getList<AgentTemplate>(this.config, "/agent-templates", params);
  }

  /** Fetch a single agent template by ID. */
  get(templateId: string): Promise<AgentTemplate> {
    return get<AgentTemplate>(this.config, `/agent-templates/${templateId}`);
  }

  /** Create a new agent template. */
  create(data: AgentTemplateCreate): Promise<AgentTemplate> {
    return post<AgentTemplate>(this.config, "/agent-templates", data);
  }

  /** Delete an agent template (admin/owner). */
  delete(templateId: string): Promise<void> {
    return del<void>(this.config, `/agent-templates/${templateId}`);
  }
}

/** Operations against `/api/v1/workforce-templates`. */
export class TemplateResource {
  private readonly config: ResolvedConfig;
  /** Nested agent-templates sub-resource. */
  readonly agents: AgentTemplateResource;

  constructor(config: ResolvedConfig) {
    this.config = config;
    this.agents = new AgentTemplateResource(config);
  }

  /** List available workforce templates. */
  list(
    options: { category?: string; offset?: number; limit?: number } = {},
  ): Promise<WorkforceTemplate[]> {
    const params = dropUndefined({
      category: options.category,
      offset: options.offset ?? 0,
      limit: options.limit ?? 50,
    });
    return getList<WorkforceTemplate>(
      this.config,
      "/workforce-templates",
      params,
    );
  }

  /** Fetch a single workforce template by ID. */
  get(templateId: string): Promise<WorkforceTemplate> {
    return get<WorkforceTemplate>(
      this.config,
      `/workforce-templates/${templateId}`,
    );
  }

  /** Create a new workforce template. */
  create(data: WorkforceTemplateCreate): Promise<WorkforceTemplate> {
    return post<WorkforceTemplate>(this.config, "/workforce-templates", data);
  }

  /**
   * Instantiate a workforce template into a new workforce.
   *
   * Returns a lightweight summary (id, name, description, agents_created,
   * edges_created). Use `client.workforces.get(id)` to fetch the full
   * workforce afterwards.
   */
  instantiate(
    templateId: string,
    name: string,
  ): Promise<TemplateInstantiateResult> {
    return post<TemplateInstantiateResult>(
      this.config,
      `/workforce-templates/${templateId}/instantiate`,
      { name },
    );
  }

  /** Delete a workforce template (admin/owner). */
  delete(templateId: string): Promise<void> {
    return del<void>(this.config, `/workforce-templates/${templateId}`);
  }
}

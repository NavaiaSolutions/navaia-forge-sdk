/**
 * Tools resource — library CRUD plus workforce attach/detach composition.
 */

import { del, get, getList, post, put, request } from "../http.js";
import type {
  ResolvedConfig,
  Tool,
  ToolCreate,
  ToolUpdate,
  WorkforceToolLink,
} from "../types.js";

export class ToolsResource {
  private readonly config: ResolvedConfig;

  constructor(config: ResolvedConfig) {
    this.config = config;
  }

  // ── Library CRUD ──────────────────────────────────────

  /** List every tool in the caller's library. */
  list(): Promise<Tool[]> {
    return getList<Tool>(this.config, "/tools");
  }

  /** List featured / template tools. */
  listFeatured(): Promise<Tool[]> {
    return getList<Tool>(this.config, "/tools/featured");
  }

  /** Fetch a tool by ID. */
  get(toolId: string): Promise<Tool> {
    return get<Tool>(this.config, `/tools/${toolId}`);
  }

  /** Register a new tool in the library. */
  create(data: ToolCreate): Promise<Tool> {
    return post<Tool>(this.config, "/tools", data);
  }

  /** Update a tool (server uses PUT). */
  update(toolId: string, data: ToolUpdate): Promise<Tool> {
    return put<Tool>(this.config, `/tools/${toolId}`, data);
  }

  /** Delete a tool from the library. */
  delete(toolId: string): Promise<void> {
    return del<void>(this.config, `/tools/${toolId}`);
  }

  // ── Workforce composition ─────────────────────────────

  /** List tools currently attached to a workforce (with overrides). */
  async listWorkforceTools(workforceId: string): Promise<WorkforceToolLink[]> {
    const result = await request<WorkforceToolLink[] | null>(
      this.config,
      "GET",
      `/workforces/${workforceId}/tools`,
    );
    return Array.isArray(result) ? result : [];
  }

  /** Attach a tool to a workforce, optionally with config overrides. */
  attachToWorkforce(
    workforceId: string,
    toolId: string,
    overrideJson?: Record<string, unknown>,
  ): Promise<WorkforceToolLink> {
    const body: Record<string, unknown> = { tool_id: toolId };
    if (overrideJson !== undefined) {
      body["override_json"] = overrideJson;
    }
    return post<WorkforceToolLink>(
      this.config,
      `/workforces/${workforceId}/tools`,
      body,
    );
  }

  /** Detach a tool from a workforce. */
  detachFromWorkforce(workforceId: string, toolId: string): Promise<void> {
    return del<void>(
      this.config,
      `/workforces/${workforceId}/tools/${toolId}`,
    );
  }
}

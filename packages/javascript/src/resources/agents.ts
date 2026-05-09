/**
 * Agent resource — CRUD plus library and workforce-membership operations.
 */

import { del, get, getList, post, put } from "../http.js";
import type {
  Agent,
  AgentCreate,
  AgentUpdate,
  ResolvedConfig,
  WorkforceMember,
} from "../types.js";

export class AgentResource {
  private readonly config: ResolvedConfig;

  constructor(config: ResolvedConfig) {
    this.config = config;
  }

  // ── Core CRUD ────────────────────────────────────────────

  /**
   * List agents, optionally filtered by workforce.
   *
   * @param workforceId - If provided, only agents in this workforce are returned.
   */
  list(workforceId?: string): Promise<Agent[]> {
    const params = workforceId ? { workforce_id: workforceId } : undefined;
    return getList<Agent>(this.config, "/agents", params);
  }

  /** List featured / template agents. */
  listFeatured(): Promise<Agent[]> {
    return getList<Agent>(this.config, "/agents/featured");
  }

  /** Get a single agent by ID. */
  get(agentId: string): Promise<Agent> {
    return get<Agent>(this.config, `/agents/${agentId}`);
  }

  /** Create a new agent. */
  create(data: AgentCreate): Promise<Agent> {
    return post<Agent>(this.config, "/agents", data);
  }

  /** Update an existing agent (server uses PUT). */
  update(agentId: string, data: AgentUpdate): Promise<Agent> {
    return put<Agent>(this.config, `/agents/${agentId}`, data);
  }

  /** Delete an agent. */
  delete(agentId: string): Promise<void> {
    return del<void>(this.config, `/agents/${agentId}`);
  }

  // ── Library operations ──────────────────────────────────

  /** Clone a featured/template agent into the user's library. */
  clone(agentId: string, name?: string): Promise<Agent> {
    const body: Record<string, unknown> = {};
    if (name !== undefined) {
      body["name"] = name;
    }
    return post<Agent>(this.config, `/agents/${agentId}/clone`, body);
  }

  /** Export an agent (returns the raw export envelope). */
  export(agentId: string): Promise<Record<string, unknown>> {
    return get<Record<string, unknown>>(
      this.config,
      `/agents/${agentId}/export`,
    );
  }

  // ── Workforce membership ────────────────────────────────

  /** List agents attached to a workforce, with per-workforce metadata. */
  listWorkforceMembers(workforceId: string): Promise<WorkforceMember[]> {
    return get<WorkforceMember[]>(
      this.config,
      `/workforces/${workforceId}/members`,
    );
  }

  /** Attach a library agent to a workforce. */
  attachToWorkforce(
    workforceId: string,
    agentId: string,
    options: {
      override_json?: Record<string, unknown>;
      position_x?: number;
      position_y?: number;
    } = {},
  ): Promise<WorkforceMember> {
    return post<WorkforceMember>(
      this.config,
      `/workforces/${workforceId}/members`,
      {
        agent_id: agentId,
        override_json: options.override_json ?? {},
        position_x: options.position_x ?? 0,
        position_y: options.position_y ?? 0,
      },
    );
  }

  /** Detach an agent from a workforce. */
  detachFromWorkforce(workforceId: string, agentId: string): Promise<void> {
    return del<void>(
      this.config,
      `/workforces/${workforceId}/members/${agentId}`,
    );
  }
}

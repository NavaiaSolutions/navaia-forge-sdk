/**
 * Agent resource — CRUD operations for agents within a workforce.
 */

import { del, get, getList, patch, post } from "../http.js";
import type {
  Agent,
  AgentCreate,
  AgentUpdate,
  ResolvedConfig,
} from "../types.js";

export class AgentResource {
  private readonly config: ResolvedConfig;

  constructor(config: ResolvedConfig) {
    this.config = config;
  }

  /**
   * List agents, optionally filtered by workforce.
   *
   * @param workforceId - If provided, only agents in this workforce are returned.
   */
  list(workforceId?: string): Promise<Agent[]> {
    const params = workforceId ? { workforce_id: workforceId } : undefined;
    return getList<Agent>(this.config, "/agents", params);
  }

  /** Get a single agent by ID. */
  get(agentId: string): Promise<Agent> {
    return get<Agent>(this.config, `/agents/${agentId}`);
  }

  /** Create a new agent. */
  create(data: AgentCreate): Promise<Agent> {
    return post<Agent>(this.config, "/agents", data);
  }

  /** Update an existing agent. */
  update(agentId: string, data: AgentUpdate): Promise<Agent> {
    return patch<Agent>(this.config, `/agents/${agentId}`, data);
  }

  /** Delete an agent. */
  delete(agentId: string): Promise<void> {
    return del<void>(this.config, `/agents/${agentId}`);
  }
}

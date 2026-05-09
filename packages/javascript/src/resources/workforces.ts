/**
 * Workforce resource — CRUD operations, plus the nested `edges` sub-resource.
 */

import { del, get, getList, post, put } from "../http.js";
import type {
  Edge,
  EdgeCreate,
  EdgeUpdate,
  ResolvedConfig,
  Workforce,
  WorkforceCreate,
  WorkforceFull,
  WorkforceUpdate,
} from "../types.js";

/** CRUD for workforce edges (graph topology between agents). */
export class EdgesResource {
  private readonly config: ResolvedConfig;

  constructor(config: ResolvedConfig) {
    this.config = config;
  }

  /** Create an edge between two agents in a workforce. */
  create(data: EdgeCreate): Promise<Edge> {
    const body: Record<string, unknown> = {
      workforce_id: data.workforce_id,
      source_agent_id: data.source_agent_id,
      target_agent_id: data.target_agent_id,
      approval_mode: data.approval_mode ?? "auto_run",
      label: data.label ?? "",
      task_mode: data.task_mode ?? "sequential",
    };
    if (data.condition_expr !== undefined) {
      body["condition_expr"] = data.condition_expr;
    }
    if (data.max_runs !== undefined) {
      body["max_runs"] = data.max_runs;
    }
    return post<Edge>(this.config, "/edges", body);
  }

  /** Patch an edge with the supplied fields (server uses PUT). */
  update(edgeId: string, data: EdgeUpdate): Promise<Edge> {
    return put<Edge>(this.config, `/edges/${edgeId}`, data);
  }

  /** Delete an edge. */
  delete(edgeId: string): Promise<void> {
    return del<void>(this.config, `/edges/${edgeId}`);
  }

  /**
   * List edges for a workforce.
   *
   * The backend has no dedicated list endpoint; this fetches the
   * workforce's `/full` view and returns its `edges` array.
   */
  async list(workforceId: string): Promise<Edge[]> {
    const full = await get<WorkforceFull>(
      this.config,
      `/workforces/${workforceId}/full`,
    );
    return full.edges ?? [];
  }
}

export class WorkforceResource {
  private readonly config: ResolvedConfig;
  /** Nested edges sub-resource. */
  readonly edges: EdgesResource;

  constructor(config: ResolvedConfig) {
    this.config = config;
    this.edges = new EdgesResource(config);
  }

  /** List all workforces. */
  list(): Promise<Workforce[]> {
    return getList<Workforce>(this.config, "/workforces");
  }

  /** Get a single workforce by ID. */
  get(workforceId: string): Promise<Workforce> {
    return get<Workforce>(this.config, `/workforces/${workforceId}`);
  }

  /** Get a workforce with its agents and edges. */
  getFull(workforceId: string): Promise<WorkforceFull> {
    return get<WorkforceFull>(this.config, `/workforces/${workforceId}/full`);
  }

  /** Create a new workforce. */
  create(data: WorkforceCreate): Promise<Workforce> {
    return post<Workforce>(this.config, "/workforces", data);
  }

  /** Update an existing workforce (server uses PUT). */
  update(workforceId: string, data: WorkforceUpdate): Promise<Workforce> {
    return put<Workforce>(this.config, `/workforces/${workforceId}`, data);
  }

  /** Delete a workforce. */
  delete(workforceId: string): Promise<void> {
    return del<void>(this.config, `/workforces/${workforceId}`);
  }
}

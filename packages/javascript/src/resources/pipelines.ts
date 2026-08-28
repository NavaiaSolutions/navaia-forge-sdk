/**
 * Pipelines resource — CRUD, run trigger, and run history.
 *
 * Wraps the platform's pipelines API (`/pipelines`, `/pipelines/{id}/run`,
 * `/pipelines/{id}/runs`). Mirrors the Python `client.pipelines` resource.
 */

import { del, get, patch, post } from "../http.js";
import type {
  PaginatedResponse,
  Pipeline,
  PipelineCreate,
  PipelineRun,
  PipelineRunReport,
  PipelineUpdate,
  ResolvedConfig,
} from "../types.js";

export class PipelineResource {
  private readonly config: ResolvedConfig;

  constructor(config: ResolvedConfig) {
    this.config = config;
  }

  /**
   * Unwrap a list endpoint that may return either a bare array or a
   * `{ items, total }` envelope. Tolerant by design — the pipelines routes'
   * exact response shape should be confirmed against the backend; until then
   * this keeps the client robust to either form (matching the Python
   * transport's `get_list`).
   */
  private async unwrapList<T>(
    path: string,
    params?: Record<string, string>,
  ): Promise<T[]> {
    const result = await get<T[] | PaginatedResponse<T> | null>(
      this.config,
      path,
      params,
    );
    if (Array.isArray(result)) {
      return result;
    }
    if (result && Array.isArray((result as PaginatedResponse<T>).items)) {
      return (result as PaginatedResponse<T>).items;
    }
    return [];
  }

  // ── CRUD ──────────────────────────────────────────────

  /** List pipelines, optionally scoped to a single workforce. */
  list(workforceId?: string): Promise<Pipeline[]> {
    const path = workforceId
      ? `/workforces/${workforceId}/pipelines`
      : "/pipelines";
    return this.unwrapList<Pipeline>(path);
  }

  /** Fetch a single pipeline by ID. */
  get(pipelineId: string): Promise<Pipeline> {
    return get<Pipeline>(this.config, `/pipelines/${pipelineId}`);
  }

  /** Create a new pipeline. */
  create(data: PipelineCreate): Promise<Pipeline> {
    return post<Pipeline>(this.config, "/pipelines", data);
  }

  /** Update a pipeline (server uses PATCH). */
  update(pipelineId: string, data: PipelineUpdate): Promise<Pipeline> {
    return patch<Pipeline>(this.config, `/pipelines/${pipelineId}`, data);
  }

  /** Delete a pipeline. */
  delete(pipelineId: string): Promise<void> {
    return del<void>(this.config, `/pipelines/${pipelineId}`);
  }

  // ── Runs ──────────────────────────────────────────────

  /** Trigger a run of a pipeline. */
  run(pipelineId: string): Promise<PipelineRun> {
    return post<PipelineRun>(this.config, `/pipelines/${pipelineId}/run`);
  }

  /**
   * List a pipeline's run history (newest first).
   *
   * @param pipelineId - The pipeline whose runs to list.
   * @param limit - Optional cap on the number of runs returned.
   */
  listRuns(pipelineId: string, limit?: number): Promise<PipelineRun[]> {
    const params: Record<string, string> = {};
    if (limit !== undefined) {
      params["limit"] = String(limit);
    }
    return this.unwrapList<PipelineRun>(`/pipelines/${pipelineId}/runs`, params);
  }

  /**
   * Report an externally-executed run back to the platform (runner ingest).
   *
   * Used by out-of-band runners to record the outcome of a run they executed
   * themselves, rather than triggering one via {@link run}.
   */
  reportRun(
    pipelineId: string,
    data: PipelineRunReport,
  ): Promise<PipelineRun> {
    return post<PipelineRun>(
      this.config,
      `/pipelines/${pipelineId}/runs`,
      data,
    );
  }
}

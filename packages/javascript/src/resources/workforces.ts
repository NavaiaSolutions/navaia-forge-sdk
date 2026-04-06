/**
 * Workforce resource — CRUD operations for workforces.
 */

import { del, get, getList, patch, post } from "../http.js";
import type {
  ResolvedConfig,
  Workforce,
  WorkforceCreate,
  WorkforceFull,
  WorkforceUpdate,
} from "../types.js";

export class WorkforceResource {
  private readonly config: ResolvedConfig;

  constructor(config: ResolvedConfig) {
    this.config = config;
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

  /** Update an existing workforce. */
  update(workforceId: string, data: WorkforceUpdate): Promise<Workforce> {
    return patch<Workforce>(this.config, `/workforces/${workforceId}`, data);
  }

  /** Delete a workforce. */
  delete(workforceId: string): Promise<void> {
    return del<void>(this.config, `/workforces/${workforceId}`);
  }
}

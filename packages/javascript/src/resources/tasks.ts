/**
 * Task resource — CRUD, approval/rejection, retry, and polling.
 */

import { TimeoutError } from "../errors.js";
import { get, getList, post } from "../http.js";
import type {
  ResolvedConfig,
  Task,
  TaskCreate,
  TaskLog,
  WaitForCompletionOptions,
} from "../types.js";

/** Terminal task statuses that stop polling. */
const TERMINAL_STATUSES: ReadonlySet<string> = new Set([
  "done",
  "failed",
  "cancelled",
  "waiting_question",
  "waiting_plan",
  "waiting_blocked",
]);

export class TaskResource {
  private readonly config: ResolvedConfig;

  constructor(config: ResolvedConfig) {
    this.config = config;
  }

  /**
   * List tasks for a workforce, optionally filtered by status.
   *
   * @param workforceId - The workforce whose tasks to list.
   * @param status - Optional status filter.
   */
  list(workforceId: string, status?: string): Promise<Task[]> {
    const params: Record<string, string> = {};
    if (status) {
      params["status"] = status;
    }
    return getList<Task>(
      this.config,
      `/workforces/${workforceId}/tasks`,
      params,
    );
  }

  /** Get a single task by ID. */
  get(taskId: string): Promise<Task> {
    return get<Task>(this.config, `/tasks/${taskId}`);
  }

  /** Create a new task.
   *
   * Posts to ``/workforces/{workforce_id}/tasks`` (matching the live backend
   * route — ``POST /tasks`` returns 404 in production).
   */
  create(data: TaskCreate): Promise<Task> {
    return post<Task>(
      this.config,
      `/workforces/${data.workforce_id}/tasks`,
      data,
    );
  }

  /** Approve a task that is waiting for plan/question approval. */
  approve(taskId: string): Promise<Task> {
    return post<Task>(this.config, `/tasks/${taskId}/approve`);
  }

  /**
   * Reject a task or plan.
   *
   * @param taskId - The task to reject.
   * @param reason - Optional rejection reason.
   */
  reject(taskId: string, reason = ""): Promise<Task> {
    return post<Task>(this.config, `/tasks/${taskId}/reject`, { reason });
  }

  /** Retry a failed task. */
  retry(taskId: string): Promise<Task> {
    return post<Task>(this.config, `/tasks/${taskId}/retry`);
  }

  /** Get the event log for a task. */
  logs(taskId: string): Promise<TaskLog[]> {
    return get<TaskLog[]>(this.config, `/tasks/${taskId}/logs`);
  }

  /**
   * Poll until a task reaches a terminal state.
   *
   * @param taskId - The task to wait for.
   * @param options - Polling interval and timeout configuration.
   * @returns The completed task.
   * @throws {@link TimeoutError} if the task does not complete within the timeout.
   *
   * @example
   * ```ts
   * const result = await nf.tasks.waitForCompletion(task.id, {
   *   pollInterval: 3000,
   *   timeout: 120_000,
   * });
   * ```
   */
  async waitForCompletion(
    taskId: string,
    options: WaitForCompletionOptions = {},
  ): Promise<Task> {
    const pollInterval = options.pollInterval ?? 5_000;
    const timeout = options.timeout ?? 300_000;
    const start = Date.now();

    while (Date.now() - start < timeout) {
      const task = await this.get(taskId);
      if (TERMINAL_STATUSES.has(task.status)) {
        return task;
      }
      await sleep(pollInterval);
    }

    throw new TimeoutError(
      `Task ${taskId} did not complete within ${timeout}ms`,
    );
  }
}

/** Promise-based sleep helper. */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

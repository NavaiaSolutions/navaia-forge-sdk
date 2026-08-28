import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NavaiaForge, TaskNotRetryable } from "../src/index.js";

const TASK = {
  id: "tk_1",
  workforce_id: "wf_1",
  agent_id: null,
  title: "Review PR",
  description: "",
  status: "failed",
  priority: "standard",
  source: "api",
  result: null,
  error: "boom",
  retry_count: 0,
  metadata_json: {},
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("TaskResource.retry", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("POSTs to /tasks/{id}/retry and returns a re-queued task", async () => {
    // Manual retry re-queues the task (pending) and resets retry_count to 0,
    // restoring the auto-retry budget (matches backend request_task_retry).
    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, { ...TASK, status: "pending", retry_count: 0, error: null }),
    );
    const nf = new NavaiaForge({ apiKey: "nf_local", baseUrl: "http://local" });

    const task = await nf.tasks.retry("tk_1");

    expect(task.status).toBe("pending");
    expect(task.retry_count).toBe(0);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/v1/tasks/tk_1/retry");
    expect((init as RequestInit).method).toBe("POST");
  });

  it("surfaces a 409 as TaskNotRetryable, not a bare error", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(409, { detail: "Task is running and cannot be retried" }),
    );
    const nf = new NavaiaForge({ apiKey: "nf_local", baseUrl: "http://local" });

    await expect(nf.tasks.retry("tk_1")).rejects.toBeInstanceOf(TaskNotRetryable);
  });

  it("preserves the 409 status code and message on the typed error", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(409, { detail: "Task is running and cannot be retried" }),
    );
    const nf = new NavaiaForge({ apiKey: "nf_local", baseUrl: "http://local" });

    try {
      await nf.tasks.retry("tk_1");
      expect.unreachable("retry should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(TaskNotRetryable);
      const typed = err as TaskNotRetryable;
      expect(typed.statusCode).toBe(409);
      expect(typed.message).toContain("running");
    }
  });
});

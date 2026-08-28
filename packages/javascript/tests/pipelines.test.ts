import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NavaiaForge } from "../src/index.js";

const PIPELINE = {
  id: "pl_1",
  workforce_id: "wf_1",
  name: "Nightly report",
  description: "",
  config_json: { steps: [] },
  status: "active",
};

const RUN = {
  id: "run_1",
  pipeline_id: "pl_1",
  status: "pending",
  result: null,
  error: null,
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("PipelineResource", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("lists pipelines from the paginated envelope", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, { items: [PIPELINE], total: 1 }),
    );
    const nf = new NavaiaForge({ apiKey: "nf_local", baseUrl: "http://local" });

    const pipelines = await nf.pipelines.list();

    expect(pipelines[0].id).toBe("pl_1");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/v1/pipelines");
  });

  it("tolerates a bare-array list response and scopes to a workforce", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, [PIPELINE]));
    const nf = new NavaiaForge({ apiKey: "nf_local", baseUrl: "http://local" });

    const pipelines = await nf.pipelines.list("wf_1");

    expect(pipelines).toHaveLength(1);
    expect(fetchMock.mock.calls[0][0]).toContain(
      "/api/v1/workforces/wf_1/pipelines",
    );
  });

  it("triggers a run via POST /pipelines/{id}/run", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, RUN));
    const nf = new NavaiaForge({ apiKey: "nf_local", baseUrl: "http://local" });

    const run = await nf.pipelines.run("pl_1");

    expect(run.status).toBe("pending");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/v1/pipelines/pl_1/run");
    expect((init as RequestInit).method).toBe("POST");
  });

  it("reports an external run via POST /pipelines/{id}/runs", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(201, { ...RUN, status: "done", result: "ok" }),
    );
    const nf = new NavaiaForge({ apiKey: "nf_local", baseUrl: "http://local" });

    const run = await nf.pipelines.reportRun("pl_1", {
      status: "done",
      result: "ok",
    });

    expect(run.status).toBe("done");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/v1/pipelines/pl_1/runs");
    expect((init as RequestInit).method).toBe("POST");
  });

  it("passes the limit query param to listRuns", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, { items: [RUN], total: 1 }),
    );
    const nf = new NavaiaForge({ apiKey: "nf_local", baseUrl: "http://local" });

    await nf.pipelines.listRuns("pl_1", 5);

    expect(fetchMock.mock.calls[0][0]).toContain("limit=5");
  });
});

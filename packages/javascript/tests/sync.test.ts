import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  NavaiaForge,
  SyncConflictError,
  ValidationError,
  type WorkforceSyncBundle,
} from "../src/index.js";

const BUNDLE: WorkforceSyncBundle = {
  bundle_version: "1.0",
  exported_at: "2026-06-12T00:00:00Z",
  instance_id: "inst_local",
  content_hash: "abc123",
  workforce: {
    origin_id: "inst_local:wf_1",
    name: "Life OS",
    description: "Personal assistant",
    runtime_mode: "claude_max",
    config_json: {},
    status: "active",
  },
  agents: [
    {
      origin_id: "inst_local:ag_1",
      name: "Fitness Coach",
      role: "coach",
      instructions: "Track workouts",
    },
  ],
  edges: [],
  tasks: [],
  conversations: [],
  knowledge_bases: [],
  integrations: [],
};

const IMPORT_RESULT = {
  workforce_id: "wf_new",
  action: "created",
  agents: { created: 1, updated: 0, deleted: 0 },
  edges: { created: 0, updated: 0, deleted: 0 },
  knowledge_bases: { created: 0, updated: 0, deleted: 0 },
  integrations: { created: 0, updated: 0, deleted: 0 },
  tasks_imported: 0,
  conversations_imported: 0,
  integrations_require_setup: [],
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("SyncResource", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("exports a bundle with runtime data excluded by default", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, BUNDLE));
    const nf = new NavaiaForge({ apiKey: "nf_local", baseUrl: "http://local" });

    const bundle = await nf.sync.exportBundle("wf_1");

    expect(bundle.workforce.origin_id).toBe("inst_local:wf_1");
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("/api/v1/sync/export/wf_1");
    expect(url).toContain("include_tasks=false");
    expect(url).toContain("include_conversations=false");
  });

  it("opts into runtime data when requested", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, BUNDLE));
    const nf = new NavaiaForge({ apiKey: "nf_local", baseUrl: "http://local" });

    await nf.sync.exportBundle("wf_1", {
      includeTasks: true,
      includeConversations: true,
    });

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("include_tasks=true");
    expect(url).toContain("include_conversations=true");
  });

  it("imports a bundle and returns the result", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(201, IMPORT_RESULT));
    const nf = new NavaiaForge({ apiKey: "nf_cloud", baseUrl: "http://cloud" });

    const result = await nf.sync.importBundle(BUNDLE);

    expect(result.action).toBe("created");
    expect(result.agents.created).toBe(1);
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("/api/v1/sync/import");
    expect(url).toContain("force=false");
  });

  it("sets force=true on the import query when requested", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, IMPORT_RESULT));
    const nf = new NavaiaForge({ apiKey: "nf_cloud", baseUrl: "http://cloud" });

    await nf.sync.importBundle(BUNDLE, { force: true });

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("force=true");
  });

  it("throws SyncConflictError on 409 carrying both bundles", async () => {
    const remote = { ...BUNDLE, instance_id: "inst_cloud", content_hash: "zzz" };
    fetchMock.mockResolvedValueOnce(
      jsonResponse(409, {
        detail: { error: "sync_conflict", remote_bundle: remote },
      }),
    );
    const nf = new NavaiaForge({ apiKey: "nf_cloud", baseUrl: "http://cloud" });

    await expect(nf.sync.importBundle(BUNDLE)).rejects.toMatchObject({
      statusCode: 409,
    });

    fetchMock.mockResolvedValueOnce(
      jsonResponse(409, {
        detail: { error: "sync_conflict", remote_bundle: remote },
      }),
    );
    try {
      await nf.sync.importBundle(BUNDLE);
      expect.unreachable("should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(SyncConflictError);
      const conflict = err as SyncConflictError<WorkforceSyncBundle>;
      expect(conflict.localBundle).toBe(BUNDLE);
      expect(conflict.remoteBundle?.instance_id).toBe("inst_cloud");
    }
  });

  it("accepts a flat (non-detail) 409 body shape", async () => {
    const remote = { ...BUNDLE, instance_id: "inst_cloud" };
    fetchMock.mockResolvedValueOnce(
      jsonResponse(409, { error: "sync_conflict", remote_bundle: remote }),
    );
    const nf = new NavaiaForge({ apiKey: "nf_cloud", baseUrl: "http://cloud" });

    try {
      await nf.sync.importBundle(BUNDLE);
      expect.unreachable("should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(SyncConflictError);
      const conflict = err as SyncConflictError<WorkforceSyncBundle>;
      expect(conflict.message).toContain("sync_conflict");
      expect(conflict.remoteBundle?.instance_id).toBe("inst_cloud");
    }
  });

  it("maps non-409 import errors via errorFromStatus", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(422, { detail: "count mismatch" }),
    );
    const nf = new NavaiaForge({ apiKey: "nf_cloud", baseUrl: "http://cloud" });

    await expect(nf.sync.importBundle(BUNDLE)).rejects.toBeInstanceOf(
      ValidationError,
    );
  });

  it("push exports from local and imports into remote", async () => {
    const local = new NavaiaForge({ apiKey: "nf_local", baseUrl: "http://local" });
    const cloud = new NavaiaForge({ apiKey: "nf_cloud", baseUrl: "http://cloud" });
    fetchMock
      .mockResolvedValueOnce(jsonResponse(200, BUNDLE)) // local export
      .mockResolvedValueOnce(jsonResponse(201, IMPORT_RESULT)); // cloud import

    const result = await local.sync.push("wf_1", cloud);

    expect(result.action).toBe("created");
    expect(fetchMock.mock.calls[0][0]).toContain("http://local");
    expect(fetchMock.mock.calls[1][0]).toContain("http://cloud");
  });

  it("pull exports from remote and imports into local", async () => {
    const local = new NavaiaForge({ apiKey: "nf_local", baseUrl: "http://local" });
    const cloud = new NavaiaForge({ apiKey: "nf_cloud", baseUrl: "http://cloud" });
    fetchMock
      .mockResolvedValueOnce(jsonResponse(200, BUNDLE)) // cloud export
      .mockResolvedValueOnce(jsonResponse(200, IMPORT_RESULT)); // local import

    const result = await local.sync.pull("wf_9", cloud);

    expect(result.workforce_id).toBe("wf_new");
    expect(fetchMock.mock.calls[0][0]).toContain("http://cloud");
    expect(fetchMock.mock.calls[1][0]).toContain("http://local");
  });
});

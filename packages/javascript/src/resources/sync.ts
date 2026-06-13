/**
 * Two-way workforce sync between a local backend and the Fareegi cloud.
 *
 * The SDK client is the orchestrator — the two backends never talk to each
 * other — so {@link SyncResource.push} and {@link SyncResource.pull} simply
 * chain an export on one client with an import on the other.
 *
 * Identity is carried by `origin_id` on every entity, so a workforce can make
 * a full round-trip (push to cloud, edit in the cloud UI, pull back) without
 * duplicating. See `docs/SYNC_ARCHITECTURE_PLAN.md` for the normative spec.
 *
 * 409 handling is local to this resource: the generic transport collapses
 * error bodies into a string, which would lose the `remote_bundle` the server
 * returns on conflict. So {@link SyncResource.importBundle} uses `requestRaw`
 * to inspect the 409 body itself, throwing {@link SyncConflictError} carrying
 * both the local and remote bundles.
 */

import { SyncConflictError } from "../errors.js";
import { get, parseResponse, requestRaw } from "../http.js";
import type {
  ResolvedConfig,
  SyncImportResult,
  WorkforceSyncBundle,
} from "../types.js";

interface NavaiaForgeLike {
  readonly sync: SyncResource;
}

interface SyncTransferOptions {
  readonly includeTasks?: boolean;
  readonly includeConversations?: boolean;
}

interface ImportOptions {
  readonly force?: boolean;
}

/** Export, import, push, and pull workforce bundles across instances. */
export class SyncResource {
  private readonly config: ResolvedConfig;

  constructor(config: ResolvedConfig) {
    this.config = config;
  }

  // ── Export ─────────────────────────────────────────────────

  /** Export a workforce and all its children as a portable bundle. */
  exportBundle(
    workforceId: string,
    options: SyncTransferOptions = {},
  ): Promise<WorkforceSyncBundle> {
    return get<WorkforceSyncBundle>(
      this.config,
      `/sync/export/${workforceId}`,
      {
        include_tasks: String(options.includeTasks ?? false),
        include_conversations: String(options.includeConversations ?? false),
      },
    );
  }

  // ── Import ─────────────────────────────────────────────────

  /**
   * Import a bundle into this instance, creating or updating in place.
   *
   * Throws {@link SyncConflictError} (HTTP 409) when the target was modified
   * since the last sync and `force` is not set; the error carries both
   * `localBundle` (the bundle you tried to import) and `remoteBundle` (the
   * server's current state) so the caller can decide which side wins.
   */
  async importBundle(
    bundle: WorkforceSyncBundle,
    options: ImportOptions = {},
  ): Promise<SyncImportResult> {
    // Everything except the 409 interception is delegated to the shared
    // transport so sync never diverges from the rest of the SDK.
    const response = await requestRaw(this.config, "POST", "/sync/import", {
      body: bundle,
      params: { force: String(options.force ?? false) },
    });

    if (response.status === 409) {
      throw await buildConflictError(response, bundle);
    }
    return parseResponse<SyncImportResult>(response);
  }

  // ── Orchestrated push / pull ───────────────────────────────

  /** Export from this instance and import into `remote` (e.g. cloud). */
  async push(
    workforceId: string,
    remote: NavaiaForgeLike,
    options: SyncTransferOptions & ImportOptions = {},
  ): Promise<SyncImportResult> {
    const bundle = await this.exportBundle(workforceId, options);
    return remote.sync.importBundle(bundle, { force: options.force });
  }

  /** Export from `remote` (e.g. cloud) and import into this instance. */
  async pull(
    workforceId: string,
    remote: NavaiaForgeLike,
    options: SyncTransferOptions & ImportOptions = {},
  ): Promise<SyncImportResult> {
    const bundle = await remote.sync.exportBundle(workforceId, options);
    return this.importBundle(bundle, { force: options.force });
  }
}

/**
 * Build a {@link SyncConflictError} from a 409 response body.
 *
 * The backend wraps the conflict payload in FastAPI's `detail` key, so the
 * body is `{"detail": {"error": ..., "remote_bundle": {...}}}`. A flat
 * `{"error": ..., "remote_bundle": {...}}` shape is also accepted.
 */
async function buildConflictError(
  response: Response,
  localBundle: WorkforceSyncBundle,
): Promise<SyncConflictError<WorkforceSyncBundle>> {
  let message = "Remote was modified since last sync";
  let remoteBundle: WorkforceSyncBundle | undefined;
  try {
    const body = (await response.json()) as Record<string, unknown>;

    // Unwrap the FastAPI `detail` envelope when present.
    let inner: Record<string, unknown> = body;
    const detail = body.detail;
    if (detail && typeof detail === "object") {
      inner = detail as Record<string, unknown>;
    } else if (typeof detail === "string") {
      message = detail;
    }

    if (message === "Remote was modified since last sync") {
      const err = inner.error;
      if (typeof err === "string" && err) {
        message = err;
      }
    }
    if (inner.remote_bundle && typeof inner.remote_bundle === "object") {
      remoteBundle = inner.remote_bundle as WorkforceSyncBundle;
    }
  } catch {
    // Keep the default message when the body is not JSON.
  }
  return new SyncConflictError<WorkforceSyncBundle>(message, {
    localBundle,
    remoteBundle,
  });
}

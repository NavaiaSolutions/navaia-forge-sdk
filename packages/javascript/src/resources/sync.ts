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
 * returns on conflict. So {@link SyncResource.importBundle} issues a raw fetch
 * and parses the conflict body itself, throwing {@link SyncConflictError}
 * carrying both the local and remote bundles.
 */

import {
  errorFromStatus,
  NavaiaForgeError,
  SyncConflictError,
} from "../errors.js";
import { get } from "../http.js";
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
    const force = options.force ?? false;
    const url = new URL(`/api/v1/sync/import`, this.config.baseUrl);
    url.searchParams.set("force", String(force));

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json",
    };
    if (this.config.apiKey) {
      headers["X-API-Key"] = this.config.apiKey;
    }

    let response: Response;
    try {
      response = await fetch(url.toString(), {
        method: "POST",
        headers,
        body: JSON.stringify(bundle),
        signal: AbortSignal.timeout(this.config.timeout),
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        throw new NavaiaForgeError(
          0,
          `Request timed out after ${this.config.timeout}ms`,
        );
      }
      throw new NavaiaForgeError(0, `Network error: ${String(err)}`);
    }

    if (response.status === 409) {
      throw await buildConflictError(response, bundle);
    }

    if (!response.ok) {
      let message: string;
      try {
        const body = (await response.json()) as Record<string, string>;
        message = body.detail ?? body.error ?? response.statusText;
      } catch {
        message = response.statusText;
      }
      throw errorFromStatus(response.status, message);
    }

    if (response.status === 204) {
      return undefined as unknown as SyncImportResult;
    }
    return (await response.json()) as SyncImportResult;
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

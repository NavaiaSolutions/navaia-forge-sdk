/**
 * Forge context injection via LangChain's `RunnableConfig`.
 *
 * Why this design: LangChain already has a first-class slot for runtime
 * context — the `configurable` field on `RunnableConfig`. We piggy-back
 * on it instead of inventing a separate injection mechanism, so existing
 * LangGraph users do not have to rewrite nodes.
 *
 * Inside a node:
 *
 * ```ts
 * function searchNode(state: MyState, config: RunnableConfig) {
 *   const forge = getForgeContext(config);
 *   const hits = await forge.client.knowledge.search(forge.workforceId!, "topic");
 *   return { results: hits };
 * }
 * ```
 */

import type { NavaiaForge } from "../../client.js";

const CONFIG_KEY = "navaia_forge";

/** Frozen snapshot of Forge state available inside a LangGraph node. */
export interface ForgeContext {
  /** The {@link NavaiaForge} client for backend access. */
  readonly client: NavaiaForge;
  /** Forge workforce this run belongs to, or `null`. */
  readonly workforceId: string | null;
  /** Forge task ID this run is fulfilling, or `null`. */
  readonly taskId: string | null;
  /** Forge agent ID, when the graph models a single agent, or `null`. */
  readonly agentId: string | null;
}

export interface WithForgeContextOptions {
  readonly workforceId?: string | null;
  readonly taskId?: string | null;
  readonly agentId?: string | null;
  /** Existing `configurable` dict to layer on top of (left unmodified). */
  readonly base?: Record<string, unknown>;
}

/**
 * Build a `configurable` dict carrying a {@link ForgeContext}.
 *
 * Returns a *new* dict — the optional `base` argument is left untouched.
 */
export function withForgeContext(
  client: NavaiaForge,
  options: WithForgeContextOptions = {},
): Record<string, unknown> {
  const ctx: ForgeContext = Object.freeze({
    client,
    workforceId: options.workforceId ?? null,
    taskId: options.taskId ?? null,
    agentId: options.agentId ?? null,
  });
  const merged: Record<string, unknown> = { ...(options.base ?? {}) };
  merged[CONFIG_KEY] = ctx;
  return merged;
}

/**
 * Extract the {@link ForgeContext} from a `RunnableConfig` (or the bare
 * `configurable` dict — both shapes show up in node signatures).
 *
 * Throws if no Forge context is present; the message points at
 * {@link withForgeContext}.
 */
export function getForgeContext(config: unknown): ForgeContext {
  const configurable = extractConfigurable(config);
  const ctx = configurable[CONFIG_KEY];
  if (!isForgeContext(ctx)) {
    throw new Error(
      "No NavaiaForge context found on RunnableConfig. " +
        "Wrap your invoke call with `withForgeContext(client, ...)` " +
        "or use `LangGraphWorkforce.run(...)` which sets it for you.",
    );
  }
  return ctx;
}

function extractConfigurable(config: unknown): Record<string, unknown> {
  if (!config || typeof config !== "object") {
    return {};
  }
  const asRecord = config as Record<string, unknown>;
  const nested = asRecord["configurable"];
  if (nested && typeof nested === "object") {
    return nested as Record<string, unknown>;
  }
  return asRecord;
}

function isForgeContext(value: unknown): value is ForgeContext {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return (
    "client" in candidate &&
    "workforceId" in candidate &&
    "taskId" in candidate &&
    "agentId" in candidate
  );
}

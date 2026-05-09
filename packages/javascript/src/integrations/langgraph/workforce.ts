/**
 * Run a compiled LangGraph as a NavaiaForge workforce.
 *
 * The wrapper is deliberately thin: it takes a compiled graph plus a
 * Forge client, and on `run()` it merges a Forge callback and a Forge
 * context into the LangChain `RunnableConfig` before delegating to the
 * graph's own `invoke`. Customer graphs do not need to be modified.
 *
 * Why a wrapper at all (instead of just docs telling people to add the
 * callback themselves)?
 *
 * 1. One place for the wiring. Forgetting either the callback or the
 *    context is the most common integration mistake.
 * 2. A clean handle Forge can register as a workforce. Future backend
 *    support for `framework="langgraph"` workforces lands here without
 *    any user-side change.
 */

import type { NavaiaForge } from "../../client.js";
import { createNavaiaForgeCallback } from "./callback.js";
import { withForgeContext } from "./context.js";

/**
 * Anything that exposes `.invoke(input, config)` — i.e. a LangChain
 * Runnable, which every compiled LangGraph satisfies. We avoid importing
 * `@langchain/langgraph` directly to keep the integration framework-agnostic
 * at the type level.
 */
export interface InvokableGraph<TInput = unknown, TOutput = unknown> {
  invoke(input: TInput, config?: Record<string, unknown>): Promise<TOutput>;
}

export interface LangGraphWorkforceOptions {
  readonly name?: string;
  readonly workforceId?: string | null;
  readonly agentId?: string | null;
  readonly defaultModel?: string;
}

export interface RunOptions {
  readonly taskId?: string | null;
  /** Existing `RunnableConfig` to layer Forge plumbing on top of. */
  readonly config?: Record<string, unknown>;
}

/** A compiled LangGraph wrapped to run inside NavaiaForge. */
export class LangGraphWorkforce<TInput = unknown, TOutput = unknown> {
  private readonly graph: InvokableGraph<TInput, TOutput>;
  private readonly client: NavaiaForge;
  readonly name: string | null;
  private readonly workforceId: string | null;
  private readonly agentId: string | null;
  private readonly defaultModel: string;

  constructor(
    graph: InvokableGraph<TInput, TOutput>,
    client: NavaiaForge,
    options: LangGraphWorkforceOptions = {},
  ) {
    if (!graph || typeof graph.invoke !== "function") {
      throw new TypeError(
        "graph must expose .invoke (it should be a CompiledGraph or LangChain Runnable).",
      );
    }
    this.graph = graph;
    this.client = client;
    this.name = options.name ?? null;
    this.workforceId = options.workforceId ?? null;
    this.agentId = options.agentId ?? null;
    this.defaultModel = options.defaultModel ?? "unknown";
  }

  /**
   * Execute the graph with Forge plumbing wired in.
   *
   * `state` is passed straight to `graph.invoke`. `options.config` is
   * layered on top of the Forge-augmented config so user-supplied callbacks
   * / configurable values are preserved.
   */
  async run(state: TInput, options: RunOptions = {}): Promise<TOutput> {
    const merged = await this.buildConfig(options);
    return this.graph.invoke(state, merged);
  }

  // ── Internal ───────────────────────────────────────────

  private async buildConfig(
    options: RunOptions,
  ): Promise<Record<string, unknown>> {
    const callback = await createNavaiaForgeCallback(this.client, {
      taskId: options.taskId ?? null,
      agentId: this.agentId,
      workforceId: this.workforceId,
      defaultModel: this.defaultModel,
    });

    const base = { ...(options.config ?? {}) };
    const existingCallbacks = Array.isArray(base["callbacks"])
      ? (base["callbacks"] as unknown[])
      : [];
    base["callbacks"] = [...existingCallbacks, callback];

    const existingConfigurable =
      base["configurable"] && typeof base["configurable"] === "object"
        ? (base["configurable"] as Record<string, unknown>)
        : undefined;

    base["configurable"] = withForgeContext(this.client, {
      workforceId: this.workforceId,
      taskId: options.taskId ?? null,
      agentId: this.agentId,
      base: existingConfigurable,
    });

    return base;
  }
}

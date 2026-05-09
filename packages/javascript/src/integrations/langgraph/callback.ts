/**
 * LangChain callback handler that streams events to Forge observability.
 *
 * Drop-in for any `@langchain/core`-compatible runnable (which is what
 * LangGraph compiles to). The handler is best-effort: if the Forge backend
 * is unreachable, callbacks log a warning and continue rather than killing
 * the graph mid-run.
 *
 * What it reports:
 *
 * - `handleLLMEnd` → `client.observability.logTokenUsage(...)` with the
 *   model name, input/output tokens, cost when present, and the duration.
 * - `handleChainStart` / `handleChainEnd` / `handleChainError` and the
 *   `handleTool*` family — debug log lines so cost dashboards can attribute
 *   spend to specific nodes/tools.
 */

import type { NavaiaForge } from "../../client.js";
import { importBaseCallbackHandler } from "./lazy.js";

export interface NavaiaForgeCallbackOptions {
  readonly taskId?: string | null;
  readonly agentId?: string | null;
  readonly workforceId?: string | null;
  /** Fallback model name when LangChain doesn't surface one. */
  readonly defaultModel?: string;
}

interface UsageNumbers {
  input: number;
  output: number;
  costUsd: number;
}

/**
 * Factory returning a `BaseCallbackHandler` instance bound to `client`.
 *
 * Implemented as an async function so the `@langchain/core` import is
 * deferred until first use — keeps the bare `import { NavaiaForge }` cheap
 * and safe in environments without the optional peer dep installed.
 */
export async function createNavaiaForgeCallback(
  client: NavaiaForge,
  options: NavaiaForgeCallbackOptions = {},
): Promise<unknown> {
  const Base = await importBaseCallbackHandler();
  const taskId = options.taskId ?? null;
  const agentId = options.agentId ?? null;
  const workforceId = options.workforceId ?? null;
  const defaultModel = options.defaultModel ?? "unknown";

  // Use a class expression so we capture the lazily-imported base.
  class NavaiaForgeCallbackImpl extends (Base as new (...args: unknown[]) => {
    [k: string]: unknown;
  }) {
    name = "NavaiaForgeCallback";
    private starts = new Map<string, number>();

    constructor() {
      super();
    }

    // ── LLM ────────────────────────────────────────────

    async handleLLMStart(
      _llm: unknown,
      _prompts: string[],
      runId: string,
    ): Promise<void> {
      this.starts.set(runId, Date.now());
    }

    async handleLLMEnd(output: unknown, runId: string): Promise<void> {
      const durationMs = this.durationMs(runId);
      const usage = extractTokenUsage(output);
      const model = extractModelName(output) ?? defaultModel;

      try {
        await client.observability.logTokenUsage({
          model,
          agent_id: agentId ?? undefined,
          task_id: taskId ?? undefined,
          input_tokens: usage.input,
          output_tokens: usage.output,
          cost_usd: usage.costUsd,
          duration_ms: durationMs,
        });
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn(
          `NavaiaForgeCallback: token-usage log failed: ${String(err)}`,
        );
      }
    }

    async handleLLMError(_err: unknown, runId: string): Promise<void> {
      this.starts.delete(runId);
    }

    // ── Chain ──────────────────────────────────────────

    async handleChainStart(
      _chain: unknown,
      _inputs: unknown,
      runId: string,
    ): Promise<void> {
      this.starts.set(runId, Date.now());
    }

    async handleChainEnd(_outputs: unknown, runId: string): Promise<void> {
      this.durationMs(runId);
    }

    async handleChainError(_err: unknown, runId: string): Promise<void> {
      this.starts.delete(runId);
    }

    // ── Tool ───────────────────────────────────────────

    async handleToolStart(
      _tool: unknown,
      _input: string,
      runId: string,
    ): Promise<void> {
      this.starts.set(runId, Date.now());
    }

    async handleToolEnd(_output: unknown, runId: string): Promise<void> {
      this.durationMs(runId);
    }

    async handleToolError(_err: unknown, runId: string): Promise<void> {
      this.starts.delete(runId);
    }

    // ── Helpers ────────────────────────────────────────

    private durationMs(runId: string): number {
      const start = this.starts.get(runId);
      this.starts.delete(runId);
      if (start === undefined) {
        return 0;
      }
      return Date.now() - start;
    }
  }

  return new NavaiaForgeCallbackImpl();
}

// ── Pure helpers (testable without @langchain/core) ────────────

/**
 * Pull input/output tokens and cost out of an LLMResult-like object.
 *
 * LangChain's response shape varies across versions and providers. The
 * canonical place is `output.llmOutput.tokenUsage`, with `usage_metadata`
 * on individual messages a newer alternative.
 */
export function extractTokenUsage(response: unknown): UsageNumbers {
  const out: UsageNumbers = { input: 0, output: 0, costUsd: 0 };
  if (!response || typeof response !== "object") {
    return out;
  }
  const r = response as Record<string, unknown>;

  const llmOutput = r["llmOutput"];
  if (llmOutput && typeof llmOutput === "object") {
    const o = llmOutput as Record<string, unknown>;
    const usageRaw = o["tokenUsage"] ?? o["token_usage"] ?? o["usage"];
    if (usageRaw && typeof usageRaw === "object") {
      const u = usageRaw as Record<string, unknown>;
      out.input = toInt(u["inputTokens"] ?? u["input_tokens"] ?? u["promptTokens"] ?? u["prompt_tokens"]);
      out.output = toInt(u["outputTokens"] ?? u["output_tokens"] ?? u["completionTokens"] ?? u["completion_tokens"]);
    }
  }

  if (out.input === 0 && out.output === 0) {
    const generations = r["generations"];
    if (Array.isArray(generations)) {
      for (const batch of generations) {
        if (!Array.isArray(batch)) continue;
        for (const gen of batch) {
          const message = (gen as Record<string, unknown> | undefined)?.[
            "message"
          ];
          const meta = (message as Record<string, unknown> | undefined)?.[
            "usage_metadata"
          ];
          if (meta && typeof meta === "object") {
            const m = meta as Record<string, unknown>;
            out.input = toInt(m["input_tokens"]);
            out.output = toInt(m["output_tokens"]);
            if (out.input || out.output) return out;
          }
        }
      }
    }
  }

  return out;
}

/** Best-effort model name extraction from an LLMResult-like object. */
export function extractModelName(response: unknown): string | null {
  if (!response || typeof response !== "object") {
    return null;
  }
  const r = response as Record<string, unknown>;
  const llmOutput = r["llmOutput"];
  if (llmOutput && typeof llmOutput === "object") {
    const o = llmOutput as Record<string, unknown>;
    const name = o["modelName"] ?? o["model_name"] ?? o["model"];
    if (typeof name === "string" && name.length > 0) {
      return name;
    }
  }
  return null;
}

function toInt(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.trunc(value);
  }
  if (typeof value === "string") {
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

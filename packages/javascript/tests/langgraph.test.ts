import { describe, expect, it } from "vitest";
import { NavaiaForge } from "../src/index.js";
import {
  extractModelName,
  extractTokenUsage,
  getForgeContext,
  LangGraphWorkforce,
  withForgeContext,
} from "../src/integrations/langgraph/index.js";

describe("langgraph helpers", () => {
  it("extracts token usage from an LLMResult-like response", () => {
    const usage = extractTokenUsage({
      llmOutput: {
        tokenUsage: { inputTokens: 100, outputTokens: 50 },
        modelName: "claude-sonnet",
      },
    });
    expect(usage).toEqual({ input: 100, output: 50, costUsd: 0 });
  });

  it("falls back to per-generation usage_metadata", () => {
    const usage = extractTokenUsage({
      generations: [
        [
          {
            message: {
              usage_metadata: { input_tokens: 12, output_tokens: 7 },
            },
          },
        ],
      ],
    });
    expect(usage.input).toBe(12);
    expect(usage.output).toBe(7);
  });

  it("returns the model name when present", () => {
    expect(
      extractModelName({ llmOutput: { modelName: "gpt-4" } }),
    ).toBe("gpt-4");
    expect(extractModelName({})).toBeNull();
  });
});

describe("withForgeContext / getForgeContext", () => {
  const client = new NavaiaForge({ apiKey: "nf_test" });

  it("round-trips the Forge context through a RunnableConfig", () => {
    const configurable = withForgeContext(client, {
      workforceId: "wf_1",
      taskId: "task_1",
    });
    const ctx = getForgeContext({ configurable });
    expect(ctx.client).toBe(client);
    expect(ctx.workforceId).toBe("wf_1");
    expect(ctx.taskId).toBe("task_1");
    expect(ctx.agentId).toBeNull();
  });

  it("accepts the bare configurable shape too", () => {
    const configurable = withForgeContext(client, { agentId: "agent_x" });
    expect(getForgeContext(configurable).agentId).toBe("agent_x");
  });

  it("does not mutate the base config", () => {
    const base = { foo: "bar" };
    const out = withForgeContext(client, { base });
    expect(out).not.toBe(base);
    expect(base).toEqual({ foo: "bar" });
    expect(out["foo"]).toBe("bar");
  });

  it("throws a helpful error when context is missing", () => {
    expect(() => getForgeContext({})).toThrow(/withForgeContext/);
  });
});

describe("LangGraphWorkforce", () => {
  const client = new NavaiaForge({ apiKey: "nf_test" });

  it("rejects graphs without an invoke method", () => {
    // @ts-expect-error — testing runtime guard
    expect(() => new LangGraphWorkforce({}, client)).toThrow(/invoke/);
  });

  it("validates a graph with .invoke()", () => {
    const graph = { invoke: async () => ({ ok: true }) };
    const wf = new LangGraphWorkforce(graph, client, { name: "demo" });
    expect(wf.name).toBe("demo");
  });
});

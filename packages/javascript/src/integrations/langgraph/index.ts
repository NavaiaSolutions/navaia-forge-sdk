/**
 * LangGraph ↔ NavaiaForge integration.
 *
 * Three thin layers, each independently useful:
 *
 * 1. {@link createNavaiaForgeCallback} — a `@langchain/core` callback
 *    handler that streams LangGraph chain / LLM / tool events to Forge
 *    observability.
 * 2. {@link ForgeContext} plus {@link getForgeContext} — inject the Forge
 *    SDK client and the current task/workforce ids into LangGraph nodes
 *    via the standard `RunnableConfig.configurable` slot.
 * 3. {@link LangGraphWorkforce} — wrap a compiled graph so it runs as a
 *    Forge workforce with both of the above pre-wired.
 *
 * The `@langchain/core` import is deferred so plain `import { NavaiaForge }`
 * still works when the optional peer dep is not installed.
 *
 * @example
 * ```ts
 * import { StateGraph } from "@langchain/langgraph";
 * import { NavaiaForge } from "@navaia/forge";
 * import { LangGraphWorkforce } from "@navaia/forge/integrations/langgraph";
 *
 * const graph = new StateGraph<MyState>(...).addNode(...).compile();
 * const client = new NavaiaForge({ apiKey: "nf_..." });
 * const wf = new LangGraphWorkforce(graph, client, { name: "research-team" });
 * const result = await wf.run({ query: "..." }, { taskId: "task_123" });
 * ```
 */

export {
  createNavaiaForgeCallback,
  extractTokenUsage,
  extractModelName,
} from "./callback.js";
export type { NavaiaForgeCallbackOptions } from "./callback.js";
export {
  getForgeContext,
  withForgeContext,
} from "./context.js";
export type { ForgeContext, WithForgeContextOptions } from "./context.js";
export { LangGraphWorkforce } from "./workforce.js";
export type {
  InvokableGraph,
  LangGraphWorkforceOptions,
  RunOptions,
} from "./workforce.js";

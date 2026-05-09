/**
 * Lazy `@langchain/core` imports — keep the SDK usable without the extra.
 *
 * LangGraph users always have `@langchain/core` installed transitively. We
 * import the few symbols we need from that package only, never from
 * `@langchain/langgraph` itself, so the integration works with hand-rolled
 * runnables as well.
 */

const INSTALL_HINT =
  "LangGraph integration requires '@langchain/core'. " +
  "Install with: npm install @langchain/core";

interface LangChainCallbacksModule {
  BaseCallbackHandler: new (...args: unknown[]) => unknown;
}

let cachedModule: LangChainCallbacksModule | null = null;

/**
 * Lazily import `@langchain/core/callbacks/base` and return
 * `BaseCallbackHandler`. Throws a clear error if the peer dep is missing.
 */
export async function importBaseCallbackHandler(): Promise<
  LangChainCallbacksModule["BaseCallbackHandler"]
> {
  if (cachedModule) {
    return cachedModule.BaseCallbackHandler;
  }
  try {
    // Use a dynamic import so bundlers that don't resolve the peer dep
    // don't fail at build time.
    const moduleId = "@langchain/core/callbacks/base";
    const mod = (await import(/* @vite-ignore */ moduleId)) as
      | LangChainCallbacksModule
      | { default?: LangChainCallbacksModule };
    const resolved =
      "BaseCallbackHandler" in mod
        ? (mod as LangChainCallbacksModule)
        : (mod.default as LangChainCallbacksModule);
    if (!resolved?.BaseCallbackHandler) {
      throw new Error(INSTALL_HINT);
    }
    cachedModule = resolved;
    return resolved.BaseCallbackHandler;
  } catch (err) {
    throw new Error(`${INSTALL_HINT} (cause: ${String(err)})`);
  }
}

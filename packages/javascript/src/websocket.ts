/**
 * WebSocket client for real-time NavaiaForge events.
 *
 * Uses the native WebSocket API (available in all browsers and Node.js 22+,
 * or via `ws` polyfill in older Node versions).
 *
 * Emits typed events for task status changes, agent status, chat messages,
 * and system notifications.
 */

import type { ResolvedConfig, WsEvent, WsEventType } from "./types.js";

// ── Event emitter types ─────────────────────────────────────

/** Map of event names to their handler signatures. */
export interface WsEventMap {
  /** Any task lifecycle event (created, updated, completed, failed). */
  "task:status": (event: WsEvent) => void;
  /** Agent status changed (idle, working, error). */
  "agent:status": (event: WsEvent) => void;
  /** Chat message received. */
  "chat:message": (event: WsEvent) => void;
  /** System notification. */
  "system": (event: WsEvent) => void;
  /** Raw event — fires for every incoming message. */
  "message": (event: WsEvent) => void;
  /** WebSocket opened. */
  "open": () => void;
  /** WebSocket closed. */
  "close": (code: number, reason: string) => void;
  /** WebSocket error. */
  "error": (error: unknown) => void;
}

type EventName = keyof WsEventMap;
type Handler<K extends EventName> = WsEventMap[K];

// ── Event routing ───────────────────────────────────────────

const TASK_EVENTS: ReadonlySet<WsEventType> = new Set([
  "task_created",
  "task_completed",
  "task_failed",
  "task_updated",
]);

function routeEvent(type: string): EventName | null {
  if (TASK_EVENTS.has(type as WsEventType)) return "task:status";
  if (type === "agent_status_changed") return "agent:status";
  if (type === "chat_message") return "chat:message";
  if (type === "system") return "system";
  return null;
}

// ── NavaiaForgeWs ───────────────────────────────────────────

/**
 * Real-time WebSocket client for the NavaiaForge platform.
 *
 * @example
 * ```ts
 * const ws = new NavaiaForgeWs(config);
 * ws.on("task:status", (event) => console.log(event));
 * ws.connect();
 * ```
 */
export class NavaiaForgeWs {
  private readonly config: ResolvedConfig;
  private socket: WebSocket | null = null;
  private listeners = new Map<EventName, Set<Handler<EventName>>>();
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldReconnect = true;

  /** Maximum number of automatic reconnect attempts. */
  readonly maxReconnectAttempts = 10;

  /** Base delay between reconnect attempts in ms (doubles each attempt). */
  readonly reconnectBaseDelay = 1000;

  constructor(config: ResolvedConfig) {
    this.config = config;
  }

  // ── Connection lifecycle ────────────────────────────────

  /**
   * Open the WebSocket connection.
   *
   * If a connection is already open this is a no-op.
   */
  connect(): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      return;
    }

    this.shouldReconnect = true;

    const wsUrl = this.config.baseUrl
      .replace(/^http/, "ws")
      .replace(/\/$/, "");

    const url = this.config.apiKey
      ? `${wsUrl}/ws?api_key=${encodeURIComponent(this.config.apiKey)}`
      : `${wsUrl}/ws`;

    this.socket = new WebSocket(url);

    this.socket.onopen = () => {
      this.reconnectAttempts = 0;
      this.emit("open");
    };

    this.socket.onmessage = (event: MessageEvent) => {
      this.handleMessage(event);
    };

    this.socket.onclose = (event: CloseEvent) => {
      this.emit("close", event.code, event.reason);
      this.attemptReconnect();
    };

    this.socket.onerror = (event: Event) => {
      this.emit("error", event);
    };
  }

  /**
   * Close the WebSocket connection.
   *
   * Disables automatic reconnection.
   */
  disconnect(): void {
    this.shouldReconnect = false;
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.socket) {
      this.socket.close(1000, "Client disconnect");
      this.socket = null;
    }
  }

  /** Whether the WebSocket is currently open. */
  get connected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  // ── Event subscription ─────────────────────────────────

  /**
   * Subscribe to an event.
   *
   * @returns An unsubscribe function.
   */
  on<K extends EventName>(event: K, handler: WsEventMap[K]): () => void {
    let set = this.listeners.get(event);
    if (!set) {
      set = new Set();
      this.listeners.set(event, set);
    }
    set.add(handler as Handler<EventName>);

    return () => {
      set!.delete(handler as Handler<EventName>);
    };
  }

  /** Remove a specific handler for an event. */
  off<K extends EventName>(event: K, handler: WsEventMap[K]): void {
    this.listeners.get(event)?.delete(handler as Handler<EventName>);
  }

  /** Remove all handlers for a given event, or all events if none specified. */
  removeAllListeners(event?: EventName): void {
    if (event) {
      this.listeners.delete(event);
    } else {
      this.listeners.clear();
    }
  }

  // ── Internal ────────────────────────────────────────────

  private emit<K extends EventName>(
    event: K,
    ...args: Parameters<WsEventMap[K]>
  ): void {
    const set = this.listeners.get(event);
    if (!set) return;
    for (const handler of set) {
      try {
        (handler as (...a: unknown[]) => void)(...args);
      } catch {
        // Swallow listener errors to prevent one bad handler from
        // breaking the event loop.
      }
    }
  }

  private handleMessage(event: MessageEvent): void {
    let parsed: WsEvent;
    try {
      parsed = JSON.parse(String(event.data)) as WsEvent;
    } catch {
      return; // Ignore non-JSON messages.
    }

    // Always emit on the raw "message" channel.
    this.emit("message", parsed);

    // Route to the typed channel.
    const channel = routeEvent(parsed.type);
    if (channel) {
      this.emit(channel as "task:status", parsed);
    }
  }

  private attemptReconnect(): void {
    if (
      !this.shouldReconnect ||
      this.reconnectAttempts >= this.maxReconnectAttempts
    ) {
      return;
    }

    const delay = this.reconnectBaseDelay * Math.pow(2, this.reconnectAttempts);
    this.reconnectAttempts += 1;

    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }
}

/**
 * HTTP client wrapper built on the native fetch API.
 *
 * Works in Node.js 18+ and all modern browsers without any polyfill.
 * The module is stateless — every function takes an immutable
 * {@link ResolvedConfig} and returns a promise.
 */

import { errorFromStatus, NavaiaForgeError } from "./errors.js";
import type { HttpMethod, PaginatedResponse, ResolvedConfig } from "./types.js";

// ── Helpers ─────────────────────────────────────────────────

function buildUrl(
  baseUrl: string,
  path: string,
  params?: Record<string, string>,
): string {
  const url = new URL(`/api/v1${path}`, baseUrl);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      url.searchParams.set(key, value);
    }
  }
  return url.toString();
}

function buildHeaders(
  apiKey: string,
  extra?: Record<string, string>,
): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
  };
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  if (extra) {
    Object.assign(headers, extra);
  }
  return headers;
}

/**
 * Parse the response body and throw a typed error when the request failed.
 *
 * @internal
 */
async function parseResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T;
  }

  if (!response.ok) {
    let message: string;
    try {
      const body: unknown = await response.json();
      message =
        (body as Record<string, string>).detail ??
        (body as Record<string, string>).error ??
        response.statusText;
    } catch {
      message = response.statusText;
    }
    throw errorFromStatus(response.status, message);
  }

  return (await response.json()) as T;
}

// ── Public API ──────────────────────────────────────────────

/**
 * Execute an HTTP request against the NavaiaForge API.
 *
 * @param config - Resolved SDK configuration (frozen).
 * @param method - HTTP method.
 * @param path   - API path (e.g. "/workforces").
 * @param options - Optional body, query params, and extra headers.
 * @returns Parsed JSON response body.
 * @throws {@link NavaiaForgeError} on non-2xx responses.
 */
export async function request<T>(
  config: ResolvedConfig,
  method: HttpMethod,
  path: string,
  options: {
    body?: unknown;
    params?: Record<string, string>;
    headers?: Record<string, string>;
  } = {},
): Promise<T> {
  const url = buildUrl(config.baseUrl, path, options.params);
  const headers = buildHeaders(config.apiKey, options.headers);

  const init: RequestInit = {
    method,
    headers,
    signal: AbortSignal.timeout(config.timeout),
  };

  if (options.body !== undefined) {
    init.body = JSON.stringify(options.body);
  }

  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new NavaiaForgeError(0, `Request timed out after ${config.timeout}ms`);
    }
    throw new NavaiaForgeError(0, `Network error: ${String(err)}`);
  }

  return parseResponse<T>(response);
}

/** Convenience GET. */
export function get<T>(
  config: ResolvedConfig,
  path: string,
  params?: Record<string, string>,
): Promise<T> {
  return request<T>(config, "GET", path, { params });
}

/** GET that unwraps a paginated `{ items, total }` envelope. */
export async function getList<T>(
  config: ResolvedConfig,
  path: string,
  params?: Record<string, string>,
): Promise<T[]> {
  const result = await get<PaginatedResponse<T>>(config, path, params);
  return result.items;
}

/** Convenience POST. */
export function post<T>(
  config: ResolvedConfig,
  path: string,
  body?: unknown,
): Promise<T> {
  return request<T>(config, "POST", path, { body });
}

/** Convenience PATCH. */
export function patch<T>(
  config: ResolvedConfig,
  path: string,
  body?: unknown,
): Promise<T> {
  return request<T>(config, "PATCH", path, { body });
}

/** Convenience PUT. */
export function put<T>(
  config: ResolvedConfig,
  path: string,
  body?: unknown,
): Promise<T> {
  return request<T>(config, "PUT", path, { body });
}

/** Convenience DELETE. */
export function del<T>(
  config: ResolvedConfig,
  path: string,
): Promise<T> {
  return request<T>(config, "DELETE", path);
}

/**
 * Upload a file via multipart/form-data.
 *
 * In browsers, pass a File object. In Node.js 18+, use the built-in
 * File or Blob from `node:buffer`.
 */
export async function uploadFile<T>(
  config: ResolvedConfig,
  path: string,
  fieldName: string,
  file: Blob | File,
  fileName?: string,
): Promise<T> {
  const url = buildUrl(config.baseUrl, path);
  const formData = new FormData();

  if (fileName) {
    formData.append(fieldName, file, fileName);
  } else {
    formData.append(fieldName, file);
  }

  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (config.apiKey) {
    headers["X-API-Key"] = config.apiKey;
  }
  // Do NOT set Content-Type — let the runtime set the multipart boundary.

  const response = await fetch(url, {
    method: "POST",
    headers,
    body: formData,
    signal: AbortSignal.timeout(config.timeout),
  });

  return parseResponse<T>(response);
}

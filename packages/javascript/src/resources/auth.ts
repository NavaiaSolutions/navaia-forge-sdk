/**
 * Auth resource — register / login / refresh / me / api-keys / validate.
 *
 * All endpoints live under `/api/v1/auth/*`. SDK callers usually
 * authenticate with a long-lived API key (via `X-API-Key`), but the
 * JWT flow is exposed so callers can build a UI on top of the SDK.
 */

import { get, post } from "../http.js";
import type {
  ApiKeyCreated,
  ApiKeyValidation,
  ResolvedConfig,
  TokenPair,
  User,
} from "../types.js";

export class AuthResource {
  private readonly config: ResolvedConfig;

  constructor(config: ResolvedConfig) {
    this.config = config;
  }

  // ── Profile ──────────────────────────────────────────────

  /** Return the currently authenticated user's profile. */
  me(): Promise<User> {
    return get<User>(this.config, "/auth/me");
  }

  // ── Email / password flows ───────────────────────────────

  /** Register a new email/password user. */
  register(input: {
    name: string;
    email: string;
    password: string;
  }): Promise<TokenPair> {
    return post<TokenPair>(this.config, "/auth/register", input);
  }

  /** Log in with email and password. */
  login(input: { email: string; password: string }): Promise<TokenPair> {
    return post<TokenPair>(this.config, "/auth/login", input);
  }

  /** Exchange a refresh token for a new access/refresh pair. */
  refresh(refreshToken: string): Promise<TokenPair> {
    return post<TokenPair>(this.config, "/auth/refresh", {
      refresh_token: refreshToken,
    });
  }

  // ── API keys ─────────────────────────────────────────────

  /**
   * Generate a new API key. The plaintext `api_key` is shown exactly once —
   * store it securely.
   */
  createKey(name = "default"): Promise<ApiKeyCreated> {
    return post<ApiKeyCreated>(this.config, "/auth/keys", { name });
  }

  /** Validate the current API key (or JWT) attached to the client. */
  validate(): Promise<ApiKeyValidation> {
    return get<ApiKeyValidation>(this.config, "/auth/validate");
  }

  // ── OAuth (helpers — return URLs for UI to redirect to) ──

  /** Return the Google OAuth start URL (`GET /auth/google`). */
  googleLoginUrl(): string {
    return this.oauthStartUrl("google");
  }

  /** Return the GitHub OAuth start URL (`GET /auth/github`). */
  githubLoginUrl(): string {
    return this.oauthStartUrl("github");
  }

  private oauthStartUrl(provider: string): string {
    const base = this.config.baseUrl.replace(/\/+$/, "");
    return `${base}/api/v1/auth/${provider}`;
  }
}

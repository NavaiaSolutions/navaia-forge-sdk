/**
 * Setup / onboarding wizard resource.
 *
 * Wraps `/api/v1/setup/*`: query which onboarding paths are available,
 * run a connectivity check for a chosen path, and mark onboarding as
 * complete.
 */

import { get, post } from "../http.js";
import type {
  ResolvedConfig,
  SetupOptions,
  SetupValidateResult,
} from "../types.js";

export class SetupResource {
  private readonly config: ResolvedConfig;

  constructor(config: ResolvedConfig) {
    this.config = config;
  }

  /** Fetch which onboarding paths are enabled in this deployment. */
  options(): Promise<SetupOptions> {
    return get<SetupOptions>(this.config, "/setup/options");
  }

  /**
   * Run the connectivity check for an onboarding path.
   *
   * @param setupPath - One of `navaia_cloud`, `claude_subscription`,
   *   `api_key`, `self_hosted`, `custom_endpoint`.
   * @param config - Path-specific config (empty for cloud/subscription paths).
   */
  validate(
    setupPath: string,
    config: Record<string, unknown> = {},
  ): Promise<SetupValidateResult> {
    return post<SetupValidateResult>(this.config, "/setup/validate", {
      setup_path: setupPath,
      config,
    });
  }

  /** Mark the current user's onboarding as completed. */
  complete(): Promise<Record<string, unknown>> {
    return post<Record<string, unknown>>(this.config, "/setup/complete");
  }
}

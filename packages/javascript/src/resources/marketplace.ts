/**
 * Marketplace resource.
 *
 * The backend exposes the public marketplace catalog under
 * `/api/v1/marketplace`:
 *
 *     client.marketplace.list()                       // browse listings
 *     client.marketplace.list({ category: "sales", isFree: true })
 *     client.marketplace.get("wf_pub_1")              // listing detail
 *     const wf = await client.marketplace.install("wf_pub_1"); // copy locally
 *
 * Browsing is read-only and surfaces every workforce you have access to — your
 * own published listings plus those published by others. `install` clones the
 * listing into your own backend (returning a fresh {@link Workforce}) so you
 * can run it locally. Paid listings (`price_cents > 0`) reject install with
 * HTTP 402 until billing is wired up.
 */

import { get, getList, post } from "../http.js";
import type {
  MarketplaceListing,
  ResolvedConfig,
  Workforce,
} from "../types.js";

function dropUndefined(
  payload: Record<string, unknown>,
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(payload)) {
    if (value !== undefined && value !== null) {
      out[key] = String(value);
    }
  }
  return out;
}

/** Operations against `/api/v1/marketplace`. */
export class MarketplaceResource {
  private readonly config: ResolvedConfig;

  constructor(config: ResolvedConfig) {
    this.config = config;
  }

  /** Browse published marketplace listings. */
  list(
    options: {
      category?: string;
      search?: string;
      isFree?: boolean;
      offset?: number;
      limit?: number;
    } = {},
  ): Promise<MarketplaceListing[]> {
    const params = dropUndefined({
      category: options.category,
      search: options.search,
      is_free: options.isFree,
      offset: options.offset ?? 0,
      limit: options.limit ?? 50,
    });
    return getList<MarketplaceListing>(
      this.config,
      "/marketplace/listings",
      params,
    );
  }

  /** Fetch a single marketplace listing by workforce ID. */
  get(workforceId: string): Promise<MarketplaceListing> {
    return get<MarketplaceListing>(
      this.config,
      `/marketplace/listings/${workforceId}`,
    );
  }

  /**
   * Install a marketplace listing into your own backend.
   *
   * Clones the published workforce (agents, edges, config) into your account
   * and returns the new {@link Workforce}. Rejects paid listings (HTTP 402) and
   * is rate-limited (HTTP 429).
   */
  install(workforceId: string): Promise<Workforce> {
    return post<Workforce>(
      this.config,
      `/marketplace/listings/${workforceId}/install`,
    );
  }
}

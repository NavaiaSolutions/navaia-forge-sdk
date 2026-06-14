import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  NavaiaForge,
  NavaiaForgeError,
  NotFoundError,
  RateLimitError,
} from "../src/index.js";

const LISTING = {
  id: "wf_pub_1",
  name: "Sales Squad",
  description: "Outbound sales automation",
  tagline: "Close more deals",
  category: "sales",
  cover_url: "https://cdn.example/cover.png",
  price_cents: 0,
  currency: "usd",
  install_count: 42,
  published_at: "2026-06-01T00:00:00Z",
  seller_id: "user_9",
  seller_name: "Acme Co",
  agent_count: 4,
};

const INSTALLED_WORKFORCE = {
  id: "wf_local_99",
  name: "Sales Squad",
  description: "Outbound sales automation",
  runtime_mode: "claude_max",
  config_json: {},
  status: "active",
  is_public: false,
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("MarketplaceResource", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("browses listings and unwraps the items envelope", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, { items: [LISTING], total: 1 }),
    );
    const nf = new NavaiaForge({ apiKey: "nf_test", baseUrl: "http://local" });

    const listings = await nf.marketplace.list();

    expect(listings[0].name).toBe("Sales Squad");
    expect(listings[0].agent_count).toBe(4);
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("/api/v1/marketplace/listings");
  });

  it("forwards category, search, and isFree filters as query params", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, { items: [LISTING], total: 1 }),
    );
    const nf = new NavaiaForge({ apiKey: "nf_test", baseUrl: "http://local" });

    await nf.marketplace.list({
      category: "sales",
      search: "deals",
      isFree: true,
      limit: 10,
    });

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("category=sales");
    expect(url).toContain("search=deals");
    expect(url).toContain("is_free=true");
    expect(url).toContain("limit=10");
  });

  it("fetches a single listing by id", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, LISTING));
    const nf = new NavaiaForge({ apiKey: "nf_test", baseUrl: "http://local" });

    const listing = await nf.marketplace.get("wf_pub_1");

    expect(listing.seller_name).toBe("Acme Co");
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("/api/v1/marketplace/listings/wf_pub_1");
  });

  it("throws NotFoundError when a listing is missing", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(404, { detail: "Listing not found" }),
    );
    const nf = new NavaiaForge({ apiKey: "nf_test", baseUrl: "http://local" });

    await expect(nf.marketplace.get("missing")).rejects.toBeInstanceOf(
      NotFoundError,
    );
  });

  it("installs a listing and returns the new workforce", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(201, INSTALLED_WORKFORCE));
    const nf = new NavaiaForge({ apiKey: "nf_test", baseUrl: "http://local" });

    const wf = await nf.marketplace.install("wf_pub_1");

    expect(wf.id).toBe("wf_local_99");
    expect(wf.is_public).toBe(false);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/marketplace/listings/wf_pub_1/install");
    expect(init.method).toBe("POST");
  });

  it("rejects installing a paid listing with HTTP 402", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(402, { detail: "Payment required" }),
    );
    const nf = new NavaiaForge({ apiKey: "nf_test", baseUrl: "http://local" });

    const err = await nf.marketplace.install("wf_paid").catch((e) => e);
    expect(err).toBeInstanceOf(NavaiaForgeError);
    expect(err.statusCode).toBe(402);
  });

  it("surfaces rate limiting as RateLimitError", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(429, { detail: "Too many installs" }),
    );
    const nf = new NavaiaForge({ apiKey: "nf_test", baseUrl: "http://local" });

    await expect(nf.marketplace.install("wf_pub_1")).rejects.toBeInstanceOf(
      RateLimitError,
    );
  });
});

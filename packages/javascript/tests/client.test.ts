import { describe, expect, it } from "vitest";
import { NavaiaForge } from "../src/index.js";

describe("NavaiaForge client", () => {
  it("exposes every documented resource namespace", () => {
    const nf = new NavaiaForge({ apiKey: "nf_test" });
    expect(nf.workforces).toBeDefined();
    expect(nf.workforces.edges).toBeDefined();
    expect(nf.agents).toBeDefined();
    expect(nf.tasks).toBeDefined();
    expect(nf.conversations).toBeDefined();
    expect(nf.knowledge).toBeDefined();
    expect(nf.observability).toBeDefined();
    expect(nf.templates).toBeDefined();
    expect(nf.templates.agents).toBeDefined();
    expect(nf.integrations).toBeDefined();
    expect(nf.tools).toBeDefined();
    expect(nf.setup).toBeDefined();
    expect(nf.auth).toBeDefined();
    expect(nf.ws).toBeDefined();
  });

  it("builds OAuth URLs from the configured baseUrl", () => {
    const nf = new NavaiaForge({
      apiKey: "nf_test",
      baseUrl: "https://api.example.com/",
    });
    expect(nf.auth.googleLoginUrl()).toBe(
      "https://api.example.com/api/v1/auth/google",
    );
    expect(nf.auth.githubLoginUrl()).toBe(
      "https://api.example.com/api/v1/auth/github",
    );
  });
});

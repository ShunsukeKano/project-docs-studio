import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GET } from "@/app/auth/challenge/route";

const request = (authorization?: string) =>
  new Request("http://web.test/auth/challenge", {
    headers: authorization ? { Authorization: authorization } : {},
  });

describe("/auth/challenge", () => {
  beforeEach(() => {
    process.env.API_BASE_URL = "http://api.test";
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("asks for credentials when none were sent", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(request());

    expect(response.status).toBe(401);
    expect(response.headers.get("WWW-Authenticate")).toBe('Basic realm="studio"');
    expect(fetchMock).not.toHaveBeenCalled(); // nothing to check without credentials
  });

  it("sends the writer back to the studio when the API accepts the credentials", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("[]", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(request("Basic Zm9vOmJhcg=="));

    expect(response.status).toBe(303);
    expect(response.headers.get("Location")).toBe("/studio");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("http://api.test/api/v1/articles");
    expect((init.headers as Record<string, string>).Authorization).toBe("Basic Zm9vOmJhcg==");
  });

  it("asks again, and does not redirect, when the API rejects the credentials", async () => {
    // A redirect here would send the browser around /studio and back for ever.
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 401 })));

    const response = await GET(request("Basic d3Jvbmc6d3Jvbmc="));

    expect(response.status).toBe(401);
    expect(response.headers.get("WWW-Authenticate")).toBe('Basic realm="studio"');
    expect(response.headers.get("Location")).toBeNull();
  });

  it("says the service is unavailable, without a redirect, when the API cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));

    const response = await GET(request("Basic Zm9vOmJhcg=="));

    expect(response.status).toBe(503);
    expect(response.headers.get("Location")).toBeNull();
  });
});

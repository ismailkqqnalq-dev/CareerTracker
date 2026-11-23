import { describe, expect, it, vi } from "vitest";
import { createApiClient } from "./api.js";

function response(status, body) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
  };
}

describe("createApiClient", () => {
  it("loads all pages without changing the list response contract", async () => {
    const fetchMock = vi.fn(async (url) => {
      const offset = Number(new URL(url, "http://localhost").searchParams.get("offset"));
      const items = offset === 0 ? [{ id: 1 }, { id: 2 }] : [{ id: 3 }];
      return response(200, items);
    });
    vi.stubGlobal("fetch", fetchMock);
    const api = createApiClient();

    const items = await api.requestAll("/skills", { pageSize: 2, token: "test" });

    expect(items).toEqual([{ id: 1 }, { id: 2 }, { id: 3 }]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls.map(([url]) => new URL(url, "http://localhost").searchParams.get("offset")))
      .toEqual(["0", "2"]);
  });

  it("asks for the newest records first only when requested", async () => {
    const fetchMock = vi.fn(async () => ({ ...response(200, []), headers: { get: () => "0" } }));
    vi.stubGlobal("fetch", fetchMock);
    const api = createApiClient();

    await api.requestPage("/opportunities?q=alfa", { token: "test", newestFirst: true });
    await api.requestPage("/opportunities", { token: "test" });

    const [newest, oldest] = fetchMock.mock.calls.map(([url]) => new URL(url, "http://localhost").searchParams);
    expect(newest.get("order")).toBe("newest");
    expect(newest.get("q")).toBe("alfa");
    expect(oldest.has("order")).toBe(false);
  });

  it("exposes error_code without using detail as a decision value", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      response(409, {
        detail: "server wording can change",
        error_code: "skill_already_recognized",
      }),
    ));
    const api = createApiClient();

    await expect(api.request("/skills/suggestions", { method: "POST" }))
      .rejects.toMatchObject({ status: 409, errorCode: "skill_already_recognized" });
  });

  it("shows a friendly rate-limit message and preserves Retry-After", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ...response(429, { detail: "server detail", error_code: "rate_limited" }),
      headers: { get: () => "12" },
    }));
    const api = createApiClient();

    await expect(api.request("/auth/token"))
      .rejects.toMatchObject({
        status: 429,
        errorCode: "rate_limited",
        retryAfter: 12,
        message: expect.stringContaining("12 saniye"),
      });
  });

  it("calls the shared unauthorized handler on HTTP 401", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      response(401, { detail: "do not parse this text" }),
    ));
    const onUnauthorized = vi.fn();
    const api = createApiClient({ onUnauthorized });

    await expect(api.request("/auth/me", { token: "expired" }))
      .rejects.toMatchObject({ status: 401 });
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it("refreshes an expired session once and retries the request with the new token", async () => {
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (url.endsWith("/auth/refresh")) return response(200, { access_token: "fresh-token" });
      const auth = options.headers.get("Authorization");
      return auth === "Bearer fresh-token" ? response(200, { email: "me@example.com" }) : response(401, {});
    });
    vi.stubGlobal("fetch", fetchMock);
    const onUnauthorized = vi.fn();
    const onTokenRefreshed = vi.fn();
    const api = createApiClient({ onUnauthorized, onTokenRefreshed });

    const me = await api.request("/auth/me", { token: "expired" });

    expect(me).toEqual({ email: "me@example.com" });
    expect(onTokenRefreshed).toHaveBeenCalledWith("fresh-token");
    expect(onUnauthorized).not.toHaveBeenCalled();
    const [, refreshOptions] = fetchMock.mock.calls.find(([url]) => url.endsWith("/auth/refresh"));
    expect(refreshOptions.method).toBe("POST");
    expect(refreshOptions.headers["X-Requested-With"]).toBe("CareerTracker");
  });

  it("shares one refresh between requests that expire at the same time", async () => {
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (url.endsWith("/auth/refresh")) return response(200, { access_token: "fresh-token" });
      return options.headers.get("Authorization") === "Bearer fresh-token" ? response(200, []) : response(401, {});
    });
    vi.stubGlobal("fetch", fetchMock);
    const api = createApiClient();

    await Promise.all([
      api.request("/tasks", { token: "expired" }),
      api.request("/contacts", { token: "expired" }),
    ]);

    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/auth/refresh"))).toHaveLength(1);
  });

  it("tries once more when another tab has just rotated the refresh cookie", async () => {
    const refreshReplies = [
      response(401, { error_code: "refresh_token_rotated" }),
      response(200, { access_token: "fresh-token" }),
    ];
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (url.endsWith("/auth/refresh")) return refreshReplies.shift();
      return options.headers.get("Authorization") === "Bearer fresh-token" ? response(200, {}) : response(401, {});
    });
    vi.stubGlobal("fetch", fetchMock);
    const onUnauthorized = vi.fn();
    const api = createApiClient({ onUnauthorized });

    await api.request("/auth/me", { token: "expired" });

    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/auth/refresh"))).toHaveLength(2);
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it("does not try to refresh when the login request itself is rejected", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(401, { detail: "Invalid credentials" }));
    vi.stubGlobal("fetch", fetchMock);
    const api = createApiClient();

    await expect(api.request("/auth/token", { method: "POST", token: "irrelevant" }))
      .rejects.toMatchObject({ status: 401 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("preserves an explicitly supplied content type for binary request bodies", async () => {
    const file = new File([new Uint8Array([1, 2, 3])], "posting.png", { type: "image/png" });
    const fetchMock = vi.fn().mockResolvedValue(response(200, { text: "Python" }));
    vi.stubGlobal("fetch", fetchMock);
    const api = createApiClient();

    await api.request("/ocr/extract", {
      method: "POST",
      token: "test-token",
      headers: { "Content-Type": "image/png" },
      body: file,
    });

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/ocr/extract");
    expect(options.body).toBe(file);
    expect(options.headers.get("Content-Type")).toBe("image/png");
    expect(options.headers.get("Authorization")).toBe("Bearer test-token");
  });
});

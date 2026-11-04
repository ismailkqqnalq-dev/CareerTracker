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
});

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

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import App from "./App.jsx";

function jsonResponse(status, body) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
  };
}

describe("authenticated API requests", () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("clears an expired session on HTTP 401 without reading detail text", async () => {
    sessionStorage.setItem("careertracker_token", "expired-token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      jsonResponse(401, { detail: "this wording has no auth clue" }),
    ));
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Hesabına giriş yap" })).toBeTruthy();
    expect(sessionStorage.getItem("careertracker_token")).toBeNull();
    expect(screen.queryByText("this wording has no auth clue")).toBeNull();
  });

  it("shows candidate request failures instead of treating them as empty results", async () => {
    sessionStorage.setItem("careertracker_token", "temporary-test-token");
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
      if (url.includes("/skills/suggestions?status=pending")) {
        return jsonResponse(200, [{ id: 2, raw_name: "Pyton", normalized_name: "pyton", status: "pending", created_at: "2026-10-25T00:00:00Z" }]);
      }
      if (url.endsWith("/skills")) return jsonResponse(200, []);
      if (url.includes("/candidates")) return jsonResponse(503, { detail: "private backend detail" });
      throw new Error(`Unexpected request: ${url}`);
    }));
    render(<App />);

    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("İstek tamamlanamadı"));
    expect(screen.queryByText("private backend detail")).toBeNull();
  });
});

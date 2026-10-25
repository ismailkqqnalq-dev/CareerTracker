import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import App from "./App.jsx";

function jsonResponse(status, body) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
  };
}

function setupLoggedInApp() {
  sessionStorage.setItem("careertracker_token", "temporary-test-token");
  const fetchMock = vi.fn(async (url) => {
    if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
    if (url.includes("/skills/suggestions?status=pending")) return jsonResponse(200, []);
    if (url.endsWith("/skills")) return jsonResponse(200, []);
    throw new Error(`Unexpected request: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);
  return fetchMock;
}

describe("skill suggestion input", () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("uses response status to show that a pending suggestion was queued", async () => {
    const fetchMock = setupLoggedInApp();
    fetchMock.mockImplementation(async (url, options = {}) => {
      if (url.endsWith("/skills/suggestions") && options.method === "POST") {
        return jsonResponse(200, { id: 8, raw_name: "Rust", status: "pending", resolved_skill_id: null });
      }
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
      if (url.includes("/skills/suggestions?status=pending")) return jsonResponse(200, []);
      if (url.endsWith("/skills")) return jsonResponse(200, []);
      throw new Error(`Unexpected request: ${url}`);
    });

    fireEvent.change(await screen.findByLabelText("Beceri adı"), { target: { value: "Rust" } });
    fireEvent.click(screen.getByRole("button", { name: "Öneri gönder" }));

    expect((await screen.findByRole("status")).textContent).toContain("bekleyen önerilere eklendi");
  });

  it("shows a distinct message for accepted suggestions whose target was deleted", async () => {
    const fetchMock = setupLoggedInApp();
    fetchMock.mockImplementation(async (url, options = {}) => {
      if (url.endsWith("/skills/suggestions") && options.method === "POST") {
        return jsonResponse(200, { id: 9, raw_name: "Old variant", status: "accepted", resolved_skill_id: null });
      }
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
      if (url.includes("/skills/suggestions?status=pending")) return jsonResponse(200, []);
      if (url.endsWith("/skills")) return jsonResponse(200, []);
      throw new Error(`Unexpected request: ${url}`);
    });

    fireEvent.change(await screen.findByLabelText("Beceri adı"), { target: { value: "Old variant" } });
    fireEvent.click(screen.getByRole("button", { name: "Öneri gönder" }));

    expect((await screen.findByRole("status")).textContent).toContain("daha önce kabul edilmiş");
    expect(screen.getByRole("status").textContent).toContain("hedef beceri artık mevcut değil");
  });

  it("uses error_code to explain that a submitted skill is already recognized", async () => {
    const fetchMock = setupLoggedInApp();
    fetchMock.mockImplementation(async (url, options = {}) => {
      if (url.endsWith("/skills/suggestions") && options.method === "POST") {
        return jsonResponse(409, {
          detail: "backend wording is not a UI contract",
          error_code: "skill_already_recognized",
        });
      }
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
      if (url.includes("/skills/suggestions?status=pending")) return jsonResponse(200, []);
      if (url.endsWith("/skills")) return jsonResponse(200, []);
      throw new Error(`Unexpected request: ${url}`);
    });

    fireEvent.change(await screen.findByLabelText("Beceri adı"), { target: { value: "Python" } });
    fireEvent.click(screen.getByRole("button", { name: "Öneri gönder" }));

    expect((await screen.findByRole("alert")).textContent).toContain("zaten katalogda tanınıyor");
    expect(screen.queryByText("backend wording is not a UI contract")).toBeNull();
  });

});

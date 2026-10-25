import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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

function setupSuggestionReviewApp(patchResponse) {
  sessionStorage.setItem("careertracker_token", "temporary-test-token");
  let pending = true;
  const fetchMock = vi.fn(async (url, options = {}) => {
    if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
    if (url.includes("/skills/suggestions?status=pending")) {
      return jsonResponse(200, pending ? [{
        id: 2,
        raw_name: "Pyton",
        normalized_name: "pyton",
        status: "pending",
        created_at: "2026-10-25T00:00:00Z",
      }] : []);
    }
    if (url.endsWith("/skills")) return jsonResponse(200, [{ id: 5, name: "Python", category: "language" }]);
    if (url.includes("/skills/suggestions/2/candidates")) {
      return jsonResponse(200, [{ id: 5, name: "Python", category: "language", score: 0.9 }]);
    }
    if (url.endsWith("/skills/suggestions/2") && options.method === "PATCH") {
      const result = await patchResponse();
      if (result.ok && result.body?.status === "accepted") pending = false;
      return jsonResponse(result.status, result.body);
    }
    throw new Error(`Unexpected request: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);
  return fetchMock;
}

function deferred() {
  let resolve;
  const promise = new Promise((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
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

  it("shows a separate message for an accepted suggestion with an existing target", async () => {
    const fetchMock = setupLoggedInApp();
    fetchMock.mockImplementation(async (url, options = {}) => {
      if (url.endsWith("/skills/suggestions") && options.method === "POST") {
        return jsonResponse(200, { id: 10, raw_name: "PyTorch", status: "accepted", resolved_skill_id: 4 });
      }
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
      if (url.includes("/skills/suggestions?status=pending")) return jsonResponse(200, []);
      if (url.endsWith("/skills")) return jsonResponse(200, []);
      throw new Error(`Unexpected request: ${url}`);
    });

    fireEvent.change(await screen.findByLabelText("Beceri adı"), { target: { value: "PyTorch" } });
    fireEvent.click(screen.getByRole("button", { name: "Öneri gönder" }));

    expect((await screen.findByRole("status")).textContent).toContain("daha önce kabul edilmiş ve eşleştirilmiş");
    expect(screen.getByRole("status").textContent).not.toContain("hedef beceri artık mevcut değil");
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

  it("shows mapping success and removes the accepted suggestion from the pending list", async () => {
    const fetchMock = setupSuggestionReviewApp(async () => ({
      status: 200,
      ok: true,
      body: { id: 2, raw_name: "Pyton", status: "accepted", resolved_skill_id: 5 },
    }));

    fireEvent.click(await screen.findByRole("button", { name: /Python/ }));
    fireEvent.click(screen.getByRole("button", { name: "Eşleştirmeyi onayla" }));

    expect((await screen.findByRole("status")).textContent).toContain("Pyton” becerisi eşleştirildi");
    await waitFor(() => expect(screen.queryByText("Pyton")).toBeNull());
    expect(fetchMock.mock.calls.some(([url, options]) => url.endsWith("/skills/suggestions/2") && options?.method === "PATCH")).toBe(true);
  });

  it("shows an error and retains the suggestion if mapping response status is not accepted", async () => {
    setupSuggestionReviewApp(async () => ({
      status: 200,
      ok: true,
      body: { id: 2, raw_name: "Pyton", status: "pending", resolved_skill_id: null },
    }));

    fireEvent.click(await screen.findByRole("button", { name: /Python/ }));
    fireEvent.click(screen.getByRole("button", { name: "Eşleştirmeyi onayla" }));

    expect((await screen.findByRole("alert")).textContent).toContain("beklenen durumu döndürmedi");
    expect(screen.getByText("Pyton")).toBeTruthy();
  });

  it("shows a request error if mapping fails with a non-401 response", async () => {
    setupSuggestionReviewApp(async () => ({
      status: 503,
      ok: false,
      body: { detail: "private mapping failure" },
    }));

    fireEvent.click(await screen.findByRole("button", { name: /Python/ }));
    fireEvent.click(screen.getByRole("button", { name: "Eşleştirmeyi onayla" }));

    expect((await screen.findByRole("alert")).textContent).toContain("İstek tamamlanamadı");
    expect(screen.queryByText("private mapping failure")).toBeNull();
    expect(screen.getByText("Pyton")).toBeTruthy();
  });

  it("locks the submit button during a request and does not send twice", async () => {
    const fetchMock = setupLoggedInApp();
    const request = deferred();
    fetchMock.mockImplementation(async (url, options = {}) => {
      if (url.endsWith("/skills/suggestions") && options.method === "POST") return request.promise;
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
      if (url.includes("/skills/suggestions?status=pending")) return jsonResponse(200, []);
      if (url.endsWith("/skills")) return jsonResponse(200, []);
      throw new Error(`Unexpected request: ${url}`);
    });
    fireEvent.change(await screen.findByLabelText("Beceri adı"), { target: { value: "Rust" } });
    fireEvent.click(screen.getByRole("button", { name: "Öneri gönder" }));

    const sendingButton = await screen.findByRole("button", { name: "Gönderiliyor…" });
    expect(sendingButton.disabled).toBe(true);
    fireEvent.click(sendingButton);
    expect(fetchMock.mock.calls.filter(([url, options]) => url.endsWith("/skills/suggestions") && options?.method === "POST")).toHaveLength(1);

    request.resolve(jsonResponse(200, { id: 11, raw_name: "Rust", status: "pending", resolved_skill_id: null }));
    expect((await screen.findByRole("status")).textContent).toContain("bekleyen önerilere eklendi");
  });

  it("does not send a blank or whitespace-only skill name", async () => {
    const fetchMock = setupLoggedInApp();
    const field = await screen.findByLabelText("Beceri adı");
    const submitButton = screen.getByRole("button", { name: "Öneri gönder" });
    expect(submitButton.disabled).toBe(true);

    fireEvent.change(field, { target: { value: "   " } });
    expect(submitButton.disabled).toBe(true);
    fireEvent.submit(field.closest("form"));

    expect(fetchMock.mock.calls.some(([url, options]) => url.endsWith("/skills/suggestions") && options?.method === "POST")).toBe(false);
  });

  it("shows a helpful error instead of crashing when the network request rejects", async () => {
    sessionStorage.setItem("careertracker_token", "temporary-test-token");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(<App />);

    expect((await screen.findByRole("alert")).textContent).toContain("İstek tamamlanamadı");
    expect(screen.getByRole("heading", { name: "Beceri önerileri" })).toBeTruthy();
    expect(screen.getByLabelText("Beceri adı")).toBeTruthy();
  });

});

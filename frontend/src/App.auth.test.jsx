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

  it("keeps the login screen and shows a Turkish message for invalid credentials", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      jsonResponse(401, { detail: "Invalid credentials" }),
    ));
    render(<App />);

    fireEvent.change(screen.getByLabelText("E-posta"), { target: { value: "person@example.com" } });
    fireEvent.change(screen.getByLabelText("Şifre"), { target: { value: "WrongPass123" } });
    fireEvent.click(screen.getByRole("button", { name: "Giriş yap" }));

    expect((await screen.findByRole("alert")).textContent).toContain("E-posta veya şifre geçersiz");
    expect(screen.getByRole("heading", { name: "Hesabına giriş yap" })).toBeTruthy();
    expect(sessionStorage.getItem("careertracker_token")).toBeNull();
  });

  it("shows an email-in-use message when registration returns HTTP 409", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(409, { detail: "email already exists" }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Kayıt ol" }));
    fireEvent.change(screen.getByLabelText("E-posta"), { target: { value: "taken@example.com" } });
    fireEvent.change(screen.getByLabelText("Şifre"), { target: { value: "StrongPass123" } });
    fireEvent.click(screen.getByRole("button", { name: "Kayıt ol" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Bu e-posta ile bir hesap zaten bulunuyor");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(sessionStorage.getItem("careertracker_token")).toBeNull();
  });

  it("explains what to fix when registration is rejected as invalid", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(422, { detail: [] })));
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Kayıt ol" }));
    expect(screen.getByText("En az 8 karakter.")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("E-posta"), { target: { value: "someone@example.com" } });
    fireEvent.change(screen.getByLabelText("Şifre"), { target: { value: "StrongPass123" } });
    fireEvent.click(screen.getByRole("button", { name: "Kayıt ol" }));

    expect((await screen.findByRole("alert")).textContent).toBe("E-posta adresini kontrol et; şifre 8 ile 128 karakter arasında olmalı.");
  });

  it("shows candidate request failures instead of treating them as empty results", async () => {
    sessionStorage.setItem("careertracker_token", "temporary-test-token");
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
      if (url.includes("/skills/suggestions?status=pending")) {
        return jsonResponse(200, [{ id: 2, raw_name: "Pyton", normalized_name: "pyton", status: "pending", created_at: "2026-10-25T00:00:00Z" }]);
      }
      if (new URL(url, "http://localhost").pathname.endsWith("/skills")) return jsonResponse(200, []);
      if (url.includes("/candidates")) return jsonResponse(503, { detail: "private backend detail" });
      throw new Error(`Unexpected request: ${url}`);
    }));
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Beceri önerileri" }));

    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("İstek tamamlanamadı"));
    expect(screen.queryByText("private backend detail")).toBeNull();
  });
  it("sends remember-me with the login and remembers that this browser has a session", async () => {
    localStorage.clear();
    const fetchMock = vi.fn(async (url) => {
      if (url.endsWith("/auth/token")) return jsonResponse(200, { access_token: "new-token" });
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "person@example.com" });
      if (url.includes("/skills")) return jsonResponse(200, []);
      return jsonResponse(200, {});
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    fireEvent.change(screen.getByLabelText("E-posta"), { target: { value: "person@example.com" } });
    fireEvent.change(screen.getByLabelText("Şifre"), { target: { value: "StrongPass123" } });
    fireEvent.click(screen.getByLabelText(/Beni hatırla/));
    fireEvent.click(screen.getByRole("button", { name: "Giriş yap" }));

    expect(await screen.findByRole("button", { name: "Çıkış yap" })).toBeTruthy();
    const [, loginOptions] = fetchMock.mock.calls.find(([url]) => url.endsWith("/auth/token"));
    expect(loginOptions.body.get("remember_me")).toBe("true");
    expect(localStorage.getItem("careertracker_session")).toBe("1");
    expect(sessionStorage.getItem("careertracker_token")).toBe("new-token");
    localStorage.clear();
  });

  it("restores the session from the refresh cookie when the tab is reopened", async () => {
    localStorage.setItem("careertracker_session", "1");
    const fetchMock = vi.fn(async (url) => {
      if (url.endsWith("/auth/refresh")) return jsonResponse(200, { access_token: "restored-token" });
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "person@example.com" });
      if (url.includes("/skills")) return jsonResponse(200, []);
      return jsonResponse(200, {});
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    expect(screen.getByRole("status").textContent).toContain("Oturumun açılıyor");
    expect(await screen.findByRole("button", { name: "Çıkış yap" })).toBeTruthy();
    expect(sessionStorage.getItem("careertracker_token")).toBe("restored-token");
    localStorage.clear();
  });

  it("falls back to the login screen and forgets the hint when the session cannot be restored", async () => {
    localStorage.setItem("careertracker_session", "1");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(401, { error_code: "refresh_token_expired" })));
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Hesabına giriş yap" })).toBeTruthy();
    expect(localStorage.getItem("careertracker_session")).toBeNull();
  });

  it("signs out on the server and forgets the session hint", async () => {
    sessionStorage.setItem("careertracker_token", "temporary-test-token");
    localStorage.setItem("careertracker_session", "1");
    const fetchMock = vi.fn(async (url) => {
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "person@example.com" });
      if (url.includes("/skills")) return jsonResponse(200, []);
      if (url.endsWith("/auth/logout")) return { status: 204, ok: true, json: async () => null };
      return jsonResponse(200, {});
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Çıkış yap" }));

    expect(await screen.findByRole("heading", { name: "Hesabına giriş yap" })).toBeTruthy();
    const [, logoutOptions] = fetchMock.mock.calls.find(([url]) => url.endsWith("/auth/logout"));
    expect(logoutOptions.method).toBe("POST");
    expect(logoutOptions.headers.get("X-Requested-With")).toBe("CareerTracker");
    expect(localStorage.getItem("careertracker_session")).toBeNull();
    expect(sessionStorage.getItem("careertracker_token")).toBeNull();
  });

  it("shows a clear message when registration is disabled", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(403, {
        detail: "server wording can change",
        error_code: "registration_disabled",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Kayıt ol" }));
    fireEvent.change(screen.getByLabelText("E-posta"), { target: { value: "new@example.com" } });
    fireEvent.change(screen.getByLabelText("Şifre"), { target: { value: "StrongPass123" } });
    fireEvent.click(screen.getByRole("button", { name: "Kayıt ol" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Kayıtlar şu anda kapalı");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(sessionStorage.getItem("careertracker_token")).toBeNull();
  });

});

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App.jsx";

const TOKEN = "a".repeat(43);

function jsonResponse(status, body) {
  return { status, ok: status >= 200 && status < 300, json: async () => body, headers: { get: () => null } };
}

function calls(fetchMock, suffix) {
  return fetchMock.mock.calls.filter(([url]) => url.endsWith(suffix));
}

describe("şifremi unuttum", () => {
  beforeEach(() => {
    sessionStorage.clear();
    window.history.replaceState(null, "", "/");
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("sends a reset link for the email typed on the login screen", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(202, { detail: "ok" }));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    fireEvent.change(screen.getByLabelText("E-posta"), { target: { value: "person@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Şifremi unuttum" }));
    expect(screen.getByLabelText("E-posta").value).toBe("person@example.com");
    fireEvent.click(screen.getByRole("button", { name: "Sıfırlama bağlantısı gönder" }));

    expect((await screen.findByRole("status")).textContent).toContain("kayıtlı bir hesap varsa");
    const [[, options]] = calls(fetchMock, "/auth/password-reset/request");
    expect(JSON.parse(options.body)).toEqual({ email: "person@example.com" });

    fireEvent.click(screen.getByRole("button", { name: "Girişe dön" }));
    expect(screen.getByRole("heading", { name: "Hesabına giriş yap" })).toBeTruthy();
  });

  it("explains when password reset is not configured on the server", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      jsonResponse(503, { error_code: "password_reset_unavailable" }),
    ));
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Şifremi unuttum" }));
    fireEvent.change(screen.getByLabelText("E-posta"), { target: { value: "person@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Sıfırlama bağlantısı gönder" }));

    expect((await screen.findByRole("alert")).textContent).toContain("şu anda kullanılamıyor");
  });

  it("opens the new-password form from the email link and removes the token from the address bar", async () => {
    window.history.replaceState(null, "", `/#sifre-sifirla=${TOKEN}`);
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(204, null));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    expect(screen.getByRole("heading", { name: "Yeni şifreni belirle" })).toBeTruthy();
    expect(window.location.hash).toBe("");

    fireEvent.change(screen.getByLabelText("Yeni şifre"), { target: { value: "BrandNewPass456" } });
    fireEvent.change(screen.getByLabelText("Yeni şifre (tekrar)"), { target: { value: "BrandNewPass456" } });
    fireEvent.click(screen.getByRole("button", { name: "Şifreyi güncelle" }));

    expect(await screen.findByRole("heading", { name: "Hesabına giriş yap" })).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain("Şifren güncellendi");
    const [[, options]] = calls(fetchMock, "/auth/password-reset/confirm");
    expect(JSON.parse(options.body)).toEqual({ token: TOKEN, new_password: "BrandNewPass456" });
  });

  it("does not submit when the two passwords differ", async () => {
    window.history.replaceState(null, "", `/#sifre-sifirla=${TOKEN}`);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    fireEvent.change(screen.getByLabelText("Yeni şifre"), { target: { value: "BrandNewPass456" } });
    fireEvent.change(screen.getByLabelText("Yeni şifre (tekrar)"), { target: { value: "BrandNewPass457" } });
    fireEvent.click(screen.getByRole("button", { name: "Şifreyi güncelle" }));

    expect(screen.getByRole("alert").textContent).toContain("Şifreler aynı değil");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("offers a new link when the old one has expired", async () => {
    window.history.replaceState(null, "", `/#sifre-sifirla=${TOKEN}`);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      jsonResponse(400, { error_code: "reset_token_invalid" }),
    ));
    render(<App />);

    fireEvent.change(screen.getByLabelText("Yeni şifre"), { target: { value: "BrandNewPass456" } });
    fireEvent.change(screen.getByLabelText("Yeni şifre (tekrar)"), { target: { value: "BrandNewPass456" } });
    fireEvent.click(screen.getByRole("button", { name: "Şifreyi güncelle" }));

    fireEvent.click(await screen.findByRole("button", { name: "Yeni bağlantı iste" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Şifreni sıfırla" })).toBeTruthy());
  });
});

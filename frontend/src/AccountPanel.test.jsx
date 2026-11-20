import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import AccountPanel from "./AccountPanel.jsx";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function apiError(status, errorCode = null) {
  return Object.assign(new Error("request failed"), { status, errorCode });
}

function fillPasswordForm(current, next, repeat = next) {
  fireEvent.change(screen.getByLabelText("Mevcut şifre"), { target: { value: current } });
  fireEvent.change(screen.getByLabelText("Yeni şifre"), { target: { value: next } });
  fireEvent.change(screen.getByLabelText("Yeni şifre (tekrar)"), { target: { value: repeat } });
  fireEvent.click(screen.getByRole("button", { name: "Şifreyi değiştir" }));
}

describe("change password", () => {
  it("sends the current and new password and clears the form on success", async () => {
    const api = { request: vi.fn(async () => null) };
    render(<AccountPanel api={api} token="test-token" onAccountDeleted={vi.fn()} />);

    fillPasswordForm("StrongPass123", "NewStrongPass456");

    expect((await screen.findByRole("status")).textContent).toContain("Şifren değiştirildi");
    expect(api.request).toHaveBeenCalledWith("/auth/me/password", {
      method: "POST",
      token: "test-token",
      body: JSON.stringify({ current_password: "StrongPass123", new_password: "NewStrongPass456" }),
    });
    expect(screen.getByLabelText("Mevcut şifre").value).toBe("");
  });

  it("does not send the request when the new passwords differ", () => {
    const api = { request: vi.fn() };
    render(<AccountPanel api={api} token="test-token" onAccountDeleted={vi.fn()} />);

    fillPasswordForm("StrongPass123", "NewStrongPass456", "Different456");

    expect(screen.getByRole("alert").textContent).toContain("birbirini tutmuyor");
    expect(api.request).not.toHaveBeenCalled();
  });

  it("explains a wrong current password", async () => {
    const api = { request: vi.fn().mockRejectedValue(apiError(403, "password_confirmation_failed")) };
    render(<AccountPanel api={api} token="test-token" onAccountDeleted={vi.fn()} />);

    fillPasswordForm("WrongPass123", "NewStrongPass456");

    expect((await screen.findByRole("alert")).textContent).toBe("Mevcut şifre yanlış.");
  });
});

describe("delete account", () => {
  it("deletes the account after confirmation and signs the user out", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const api = { request: vi.fn(async () => null) };
    const onAccountDeleted = vi.fn();
    render(<AccountPanel api={api} token="test-token" onAccountDeleted={onAccountDeleted} />);

    fireEvent.change(screen.getByLabelText("Onay için şifren"), { target: { value: "StrongPass123" } });
    fireEvent.click(screen.getByRole("button", { name: "Hesabımı kalıcı olarak sil" }));

    await waitFor(() => expect(onAccountDeleted).toHaveBeenCalledTimes(1));
    expect(api.request).toHaveBeenCalledWith("/auth/me", {
      method: "DELETE",
      token: "test-token",
      body: JSON.stringify({ password: "StrongPass123" }),
    });
  });

  it("does nothing when the user cancels the confirmation", () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const api = { request: vi.fn() };
    const onAccountDeleted = vi.fn();
    render(<AccountPanel api={api} token="test-token" onAccountDeleted={onAccountDeleted} />);

    fireEvent.change(screen.getByLabelText("Onay için şifren"), { target: { value: "StrongPass123" } });
    fireEvent.click(screen.getByRole("button", { name: "Hesabımı kalıcı olarak sil" }));

    expect(api.request).not.toHaveBeenCalled();
    expect(onAccountDeleted).not.toHaveBeenCalled();
  });

  it("keeps the user signed in when the password is wrong", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const api = { request: vi.fn().mockRejectedValue(apiError(403, "password_confirmation_failed")) };
    const onAccountDeleted = vi.fn();
    render(<AccountPanel api={api} token="test-token" onAccountDeleted={onAccountDeleted} />);

    fireEvent.change(screen.getByLabelText("Onay için şifren"), { target: { value: "WrongPass123" } });
    fireEvent.click(screen.getByRole("button", { name: "Hesabımı kalıcı olarak sil" }));

    expect((await screen.findByRole("alert")).textContent).toBe("Mevcut şifre yanlış.");
    expect(onAccountDeleted).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Hesabımı kalıcı olarak sil" }).disabled).toBe(false);
  });
});

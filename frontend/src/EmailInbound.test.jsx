import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import EmailForwardingPanel from "./EmailForwardingPanel.jsx";
import EmailSuggestionsCard from "./EmailSuggestionsCard.jsx";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const disabled = { enabled: false, address: null, domain_configured: true, created_at: null, verification_code: null, verification_received_at: null };
const enabled = { ...disabled, enabled: true, address: "abc123@gelen.example.test", created_at: "2026-11-22T10:00:00Z" };

describe("email forwarding panel", () => {
  it("creates an address and shows the setup steps", async () => {
    const api = { request: vi.fn(async (path, options = {}) => (options.method === "POST" ? enabled : disabled)) };
    render(<EmailForwardingPanel api={api} token="t" />);

    fireEvent.click(await screen.findByRole("button", { name: "Yönlendirme adresi oluştur" }));

    expect(await screen.findByText("abc123@gelen.example.test")).toBeTruthy();
    expect(screen.getByText(/Henüz bir Gmail doğrulama kodu gelmedi/)).toBeTruthy();
    expect(api.request).toHaveBeenCalledWith("/email-insights/address", expect.objectContaining({ method: "POST" }));
  });

  it("shows the Gmail verification code once it arrives", async () => {
    const api = { request: vi.fn(async () => ({ ...enabled, verification_code: "987654321" })) };
    render(<EmailForwardingPanel api={api} token="t" />);

    expect((await screen.findByText(/Gmail doğrulama kodu/)).textContent).toContain("987654321");
  });

  it("explains when the server has no inbound domain yet", async () => {
    const api = { request: vi.fn(async () => ({ ...enabled, address: null, domain_configured: false })) };
    render(<EmailForwardingPanel api={api} token="t" />);

    expect(await screen.findByText(/alan adı henüz ayarlanmadı/)).toBeTruthy();
  });

  it("disables forwarding only after confirmation", async () => {
    vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    const api = { request: vi.fn(async (path, options = {}) => (options.method === "DELETE" ? null : enabled)) };
    render(<EmailForwardingPanel api={api} token="t" />);

    fireEvent.click(await screen.findByRole("button", { name: "Yönlendirmeyi kapat" }));
    expect(api.request.mock.calls.some(([, options]) => options?.method === "DELETE")).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Yönlendirmeyi kapat" }));
    expect(await screen.findByRole("button", { name: "Yönlendirme adresi oluştur" })).toBeTruthy();
  });
});

const suggestion = {
  id: 4,
  opportunity: { id: 7, company: "Trendyol", position: "Backend", status: "Teknik mülakat" },
  email_type: "ret",
  confidence: 0.99,
  sender: "ik@careers.trendyol.com",
  subject: "Başvurunuz hakkında",
  received_at: "2026-11-22T09:00:00Z",
  suggestion: { status: "Reddedildi", last_contact_date: "2026-11-22", task: null },
  state: "pending",
};

describe("email suggestions card", () => {
  it("lists pending suggestions and applies one", async () => {
    const onChanged = vi.fn();
    const api = { request: vi.fn(async (path) => (path === "/email-insights/suggestions" ? [suggestion] : { ...suggestion, state: "applied" })) };
    render(<EmailSuggestionsCard api={api} token="t" reloadKey={0} onChanged={onChanged} />);

    expect((await screen.findByText(/Trendyol · Olumsuz dönüş/)).textContent).toContain("Olumsuz dönüş");
    expect(screen.getByText(/durum → Reddedildi/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Trendyol önerisini uygula" }));

    await waitFor(() => expect(onChanged).toHaveBeenCalledOnce());
    expect(api.request).toHaveBeenCalledWith("/email-insights/suggestions/4/apply", expect.objectContaining({ method: "POST" }));
    expect(screen.queryByText(/Trendyol · Olumsuz dönüş/)).toBeNull();
  });

  it("dismisses a suggestion", async () => {
    const api = { request: vi.fn(async (path) => (path === "/email-insights/suggestions" ? [suggestion] : {})) };
    render(<EmailSuggestionsCard api={api} token="t" reloadKey={0} onChanged={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Trendyol önerisini reddet" }));

    await waitFor(() => expect(api.request).toHaveBeenCalledWith("/email-insights/suggestions/4/dismiss", expect.objectContaining({ method: "POST" })));
  });

  it("stays hidden when there is nothing to suggest or the request fails", async () => {
    const empty = { request: vi.fn(async () => []) };
    const { container, unmount } = render(<EmailSuggestionsCard api={empty} token="t" reloadKey={0} onChanged={vi.fn()} />);
    await waitFor(() => expect(empty.request).toHaveBeenCalled());
    expect(container.textContent).toBe("");
    unmount();

    const failing = { request: vi.fn().mockRejectedValue(new Error("down")) };
    const second = render(<EmailSuggestionsCard api={failing} token="t" reloadKey={0} onChanged={vi.fn()} />);
    await waitFor(() => expect(failing.request).toHaveBeenCalled());
    expect(second.container.textContent).toBe("");
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createApiClient } from "./api.js";
import ApplicationAnalyticsPanel from "./ApplicationAnalyticsPanel.jsx";

function jsonResponse(status, body) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
  };
}

function analytics(months = 12) {
  const applicationsByMonth = months === 3
    ? [
      { month: "2026-09", count: 1 },
      { month: "2026-10", count: 0 },
      { month: "2026-11", count: 2 },
    ]
    : Array.from({ length: months }, (_, index) => ({
      month: `2026-${String(index + 1).padStart(2, "0")}`,
      count: index === 0 ? 2 : 0,
    }));
  return {
    months,
    start_month: applicationsByMonth[0].month,
    end_month: applicationsByMonth.at(-1).month,
    total_applications: applicationsByMonth.reduce((sum, item) => sum + item.count, 0),
    applications_by_month: applicationsByMonth,
  };
}

describe("ApplicationAnalyticsPanel", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("loads the authenticated monthly trend and includes zero-application months", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, analytics(12)));
    vi.stubGlobal("fetch", fetchMock);
    render(<ApplicationAnalyticsPanel api={createApiClient()} token="test-token" />);

    expect(await screen.findByRole("heading", { name: "Aylık başvurular" })).toBeTruthy();
    expect(screen.getByText("2 başvuru")).toBeTruthy();
    expect(screen.getByRole("listitem", { name: "2026-01: 2 başvuru" })).toBeTruthy();
    expect(screen.getByRole("listitem", { name: "2026-02: 0 başvuru" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/analytics/applications?months=12",
      expect.objectContaining({ headers: expect.any(Headers) }),
    );
    expect(fetchMock.mock.calls[0][1].headers.get("Authorization")).toBe("Bearer test-token");
  });

  it("reloads the trend when the user changes the period", async () => {
    const fetchMock = vi.fn(async (url) => {
      const months = Number(new URL(url, "http://localhost").searchParams.get("months"));
      return jsonResponse(200, analytics(months));
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<ApplicationAnalyticsPanel api={createApiClient()} token="test-token" />);

    const period = await screen.findByLabelText("Dönem");
    fireEvent.change(period, { target: { value: "3" } });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(2);
      expect(screen.getAllByRole("listitem")).toHaveLength(3);
    });
  });

  it("shows a retry action after a request failure", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(503, { error_code: "service_unavailable" }))
      .mockResolvedValueOnce(jsonResponse(200, analytics(12)));
    vi.stubGlobal("fetch", fetchMock);
    render(<ApplicationAnalyticsPanel api={createApiClient()} token="test-token" />);

    expect((await screen.findByRole("alert")).textContent).toContain("Başvuru analizi yüklenemedi");
    fireEvent.click(screen.getByRole("button", { name: "Yeniden dene" }));

    expect(await screen.findByText("2 başvuru")).toBeTruthy();
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import OpportunityDetail from "./OpportunityDetail.jsx";
import { today } from "./crmUtils.js";

afterEach(cleanup);

const detail = {
  opportunity: {
    id: 7, company: "Trendyol", position: "Backend Developer", type: "İş", application_date: "2026-11-01",
    job_link: "https://example.test/ilan", salary: 0, location: "İzmir", status: "Teknik mülakat",
    notes: "Takım lideriyle görüşüldü", next_action: "Vaka çalışmasını gönder", last_contact_date: "2026-11-10",
  },
  contacts: [{ id: 3, name: "Ayşe Yılmaz", role: "İK", email: "ayse@example.test", linkedin: "https://www.linkedin.com/in/ayse", opportunity_id: 7 }],
  tasks: [
    { id: 5, description: "Vaka çalışması", due_date: "2026-11-25", is_completed: false, opportunity_id: 7 },
    { id: 6, description: "Özgeçmiş gönder", due_date: "2026-10-30", is_completed: true, opportunity_id: 7 },
  ],
  activities: [{ id: 9, activity_type: "Görüşme", dates: "2026-11-05", notes: "İlk görüşme", contact_id: 3, opportunity_id: 7 }],
  skills: [{ id: 1, name: "Python" }],
};

function createApi(overrides = {}) {
  return {
    request: vi.fn(async (path, options = {}) => {
      if (path === "/opportunities/7/detail") return detail;
      if (options.method) return {};
      throw new Error(`Unexpected request: ${path}`);
    }),
    ...overrides,
  };
}

function lastCall(api, path) {
  const call = [...api.request.mock.calls].reverse().find(([url]) => url === path);
  return call && { ...call[1], body: call[1].body && JSON.parse(call[1].body) };
}

describe("opportunity detail", () => {
  it("shows the opportunity, its people, skills and a merged timeline", async () => {
    const onBack = vi.fn();
    render(<OpportunityDetail api={createApi()} token="t" opportunityId={7} onBack={onBack} />);

    expect(await screen.findByRole("heading", { name: "Backend Developer" })).toBeTruthy();
    expect(screen.getByText("Trendyol")).toBeTruthy();
    expect(screen.getByText("Vaka çalışmasını gönder")).toBeTruthy();
    expect(within(screen.getByRole("region", { name: "Kişiler" })).getByText("Ayşe Yılmaz")).toBeTruthy();
    expect(within(screen.getByRole("region", { name: "İlandaki beceriler" })).getByText("Python")).toBeTruthy();
    expect(screen.getByLabelText("Başvuru durumu").value).toBe("Teknik mülakat");

    const entries = within(screen.getByRole("list", { name: "Zaman çizelgesi" })).getAllByRole("listitem");
    expect(entries.map((entry) => entry.textContent)).toEqual([
      expect.stringContaining("Vaka çalışması"),
      expect.stringContaining("İlk görüşme"),
      expect.stringContaining("Özgeçmiş gönder"),
    ]);
    expect(entries[1].textContent).toContain("Ayşe Yılmaz");

    fireEvent.click(screen.getByRole("button", { name: "← Başvurulara dön" }));
    expect(onBack).toHaveBeenCalledOnce();
  });

  it("completes a task from the timeline and reloads", async () => {
    const api = createApi();
    render(<OpportunityDetail api={api} token="t" opportunityId={7} onBack={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Vaka çalışması tamamlandı olarak işaretle" }));

    await waitFor(() => expect(lastCall(api, "/tasks/5")).toMatchObject({ method: "PATCH", body: { is_completed: true } }));
    expect((await screen.findByRole("status")).textContent).toContain("Görev tamamlandı");
    expect(api.request.mock.calls.filter(([url]) => url === "/opportunities/7/detail")).toHaveLength(2);
  });

  it("adds a task to this opportunity", async () => {
    const api = createApi();
    render(<OpportunityDetail api={api} token="t" opportunityId={7} onBack={vi.fn()} />);

    fireEvent.change(await screen.findByLabelText("Yeni görev"), { target: { value: "Teşekkür e-postası" } });
    fireEvent.change(screen.getByLabelText("Son tarih"), { target: { value: "2026-11-28" } });
    fireEvent.click(screen.getByRole("button", { name: "Görevi ekle" }));

    await waitFor(() => expect(lastCall(api, "/tasks")).toMatchObject({
      method: "POST",
      body: { description: "Teşekkür e-postası", due_date: "2026-11-28", opportunity_id: 7 },
    }));
    await waitFor(() => expect(screen.getByLabelText("Yeni görev").value).toBe(""));
  });

  it("adds a note linked to a contact", async () => {
    const api = createApi();
    render(<OpportunityDetail api={api} token="t" opportunityId={7} onBack={vi.fn()} />);

    fireEvent.change(await screen.findByLabelText("Tür"), { target: { value: "Telefon" } });
    fireEvent.change(screen.getByLabelText("İlgili kişi"), { target: { value: "3" } });
    fireEvent.change(screen.getByLabelText("Not"), { target: { value: "Teknik mülakat tarihi konuşuldu" } });
    fireEvent.click(screen.getByRole("button", { name: "Notu ekle" }));

    await waitFor(() => expect(lastCall(api, "/activities")).toMatchObject({
      method: "POST",
      body: { activity_type: "Telefon", dates: today(), notes: "Teknik mülakat tarihi konuşuldu", contact_id: 3, opportunity_id: 7 },
    }));
  });

  it("changes the status and records today's contact", async () => {
    const api = createApi();
    render(<OpportunityDetail api={api} token="t" opportunityId={7} onBack={vi.fn()} />);

    fireEvent.change(await screen.findByLabelText("Başvuru durumu"), { target: { value: "Son mülakat" } });
    await waitFor(() => expect(lastCall(api, "/opportunities/7")).toMatchObject({ method: "PATCH", body: { status: "Son mülakat" } }));

    await waitFor(() => expect(screen.getByRole("button", { name: "Bugün iletişime geçtim" }).disabled).toBe(false));
    fireEvent.click(screen.getByRole("button", { name: "Bugün iletişime geçtim" }));
    await waitFor(() => expect(lastCall(api, "/opportunities/7")).toMatchObject({ method: "PATCH", body: { last_contact_date: today() } }));
  });

  it("explains when the opportunity no longer exists", async () => {
    const api = { request: vi.fn().mockRejectedValue(Object.assign(new Error("missing"), { status: 404 })) };
    render(<OpportunityDetail api={api} token="t" opportunityId={7} onBack={vi.fn()} />);

    expect((await screen.findByRole("alert")).textContent).toContain("Bu başvuru bulunamadı");
    expect(screen.getByRole("button", { name: "← Başvurulara dön" })).toBeTruthy();
  });
});

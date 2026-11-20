import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import CrmWorkspace, { OPPORTUNITY_STATUSES } from "./CrmWorkspace.jsx";

afterEach(cleanup);

const legacyRecord = {
  id: 3,
  company: "Eski Şirket",
  position: "Stajyer",
  type: "Staj",
  application_date: "2026-10-01",
  status: "mülakat bekliyor",
  salary: 0,
  location: "İzmir",
  job_link: "",
  last_contact_date: "2026-10-01",
  next_action: "",
  notes: "",
};

function createApi(records = []) {
  return {
    requestPage: vi.fn(async () => ({ items: records, totalCount: records.length })),
    requestAll: vi.fn(async () => records),
    request: vi.fn(async () => ({})),
  };
}

describe("opportunity status field", () => {
  it("offers the fixed statuses and starts a new opportunity as applied", async () => {
    render(<CrmWorkspace api={createApi()} token="test-token" view="opportunities" onNavigate={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "+ Yeni başvuru" }));
    const status = screen.getByLabelText("Durum");

    expect(status.tagName).toBe("SELECT");
    expect(status.value).toBe("Başvuruldu");
    expect([...status.options].map((option) => option.value)).toEqual(OPPORTUNITY_STATUSES);
  });

  it("keeps a legacy free-text status selectable instead of silently replacing it", async () => {
    const api = createApi([legacyRecord]);
    render(<CrmWorkspace api={api} token="test-token" view="opportunities" onNavigate={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Düzenle" }));
    const status = screen.getByLabelText("Durum");

    expect(status.value).toBe("mülakat bekliyor");
    expect(status.options[0].textContent).toBe("mülakat bekliyor (eski değer)");
    fireEvent.change(status, { target: { value: "Teknik mülakat" } });
    expect(status.value).toBe("Teknik mülakat");
  });
});

function localToday() {
  const date = new Date();
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

function createOverviewApi() {
  const todayValue = localToday();
  const agenda = {
    tasks: [
      { id: 5, description: "Teşekkür e-postası", due_date: "2000-01-01", opportunity_id: 7, company: "Sessiz AŞ", position: "Backend" },
      { id: 6, description: "Portföyü güncelle", due_date: todayValue, opportunity_id: 7, company: "Sessiz AŞ", position: "Backend" },
    ],
    follow_ups: [
      { id: 7, company: "Sessiz AŞ", position: "Backend", status: "Başvuruldu", last_contact_date: "2000-01-01", next_action: "İK'ya yaz", days_since_contact: 15 },
    ],
  };
  return {
    requestPage: vi.fn(async () => ({ items: [], totalCount: 0 })),
    requestAll: vi.fn(async () => []),
    request: vi.fn(async (path, options = {}) => {
      if (path === "/dashboard") return { total_opportunities: 1, interview_count: 0, offer_count: 0, by_status: { "Başvuruldu": 1 } };
      if (path === `/agenda?today=${todayValue}`) return agenda;
      if (options.method === "PATCH") return {};
      throw new Error(`Unexpected request: ${path}`);
    }),
  };
}

describe("overview agenda", () => {
  it("shows overdue and today's tasks and completes one from the overview", async () => {
    const api = createOverviewApi();
    render(<CrmWorkspace api={api} token="test-token" view="overview" onNavigate={vi.fn()} />);

    expect((await screen.findByText("Teşekkür e-postası")).closest("li").textContent).toContain("Gecikti");
    expect(screen.getByText("Portföyü güncelle").closest("li").textContent).toContain("Bugün");

    fireEvent.click(screen.getByRole("button", { name: "Teşekkür e-postası tamamlandı" }));

    await waitFor(() => expect(api.request).toHaveBeenCalledWith("/tasks/5", expect.objectContaining({
      method: "PATCH",
      body: JSON.stringify({ is_completed: true }),
    })));
    await waitFor(() => expect(api.request.mock.calls.filter(([path]) => path.startsWith("/agenda")).length).toBe(2));
  });

  it("lists stale applications with their next step and records today's contact", async () => {
    const api = createOverviewApi();
    render(<CrmWorkspace api={api} token="test-token" view="overview" onNavigate={vi.fn()} />);

    const item = (await screen.findByText("Sessiz AŞ · Backend")).closest("li");
    expect(item.textContent).toContain("15 gündür temas yok");
    expect(item.textContent).toContain("Sonraki adım: İK'ya yaz");

    fireEvent.click(screen.getByRole("button", { name: "Sessiz AŞ ile bugün iletişime geçtim" }));

    await waitFor(() => expect(api.request).toHaveBeenCalledWith("/opportunities/7", expect.objectContaining({
      method: "PATCH",
      body: JSON.stringify({ last_contact_date: localToday() }),
    })));
  });
});

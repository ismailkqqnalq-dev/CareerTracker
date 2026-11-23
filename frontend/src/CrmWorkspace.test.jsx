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

describe("quick capture", () => {
  it("saves an opportunity with only company and position, sending empty optional fields as null", async () => {
    const api = createApi();
    render(<CrmWorkspace api={api} token="test-token" view="opportunities" onNavigate={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "+ Yeni başvuru" }));
    fireEvent.change(screen.getByLabelText("Şirket"), { target: { value: "Hızlı AŞ" } });
    fireEvent.change(screen.getByLabelText("Pozisyon"), { target: { value: "Backend" } });
    fireEvent.click(screen.getByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(api.request).toHaveBeenCalledWith("/opportunities", expect.objectContaining({ method: "POST" })));
    const payload = JSON.parse(api.request.mock.calls[0][1].body);
    expect(payload).toMatchObject({
      company: "Hızlı AŞ", position: "Backend", status: "Başvuruldu",
      type: null, salary: null, location: null, job_link: null, next_action: null, notes: null,
    });
    expect(payload.application_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("keeps an empty date empty when editing instead of filling in today", async () => {
    const api = createApi([{ ...legacyRecord, last_contact_date: null }]);
    render(<CrmWorkspace api={api} token="test-token" view="opportunities" onNavigate={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Düzenle" }));

    expect(screen.getByLabelText("Son iletişim tarihi").value).toBe("");
  });

  it("does not show a zero salary in the list", async () => {
    render(<CrmWorkspace api={createApi([legacyRecord])} token="test-token" view="opportunities" onNavigate={vi.fn()} />);

    await screen.findByLabelText("Eski Şirket durumu");
    expect(screen.queryByText(/ücret/)).toBeNull();
  });

  it("asks the server for the newest records first", async () => {
    const api = createApi();
    render(<CrmWorkspace api={api} token="test-token" view="tasks" onNavigate={vi.fn()} />);

    await waitFor(() => expect(api.requestPage).toHaveBeenCalled());
    expect(api.requestPage.mock.calls[0][1]).toMatchObject({ newestFirst: true, offset: 0 });
  });

  it("explains when the opportunity limit is reached", async () => {
    const api = createApi();
    api.request.mockRejectedValueOnce(Object.assign(new Error("quota"), { status: 409, errorCode: "quota_exceeded" }));
    render(<CrmWorkspace api={api} token="test-token" view="opportunities" onNavigate={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "+ Yeni başvuru" }));
    fireEvent.change(screen.getByLabelText("Şirket"), { target: { value: "Sınır AŞ" } });
    fireEvent.change(screen.getByLabelText("Pozisyon"), { target: { value: "Backend" } });
    fireEvent.click(screen.getByRole("button", { name: "Kaydet" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Başvuru sınırına ulaştın");
  });
});

describe("quick status change in the opportunity list", () => {
  it("saves a new status straight from the list and reloads it", async () => {
    const api = createApi([{ ...legacyRecord, status: "Başvuruldu" }]);
    render(<CrmWorkspace api={api} token="test-token" view="opportunities" onNavigate={vi.fn()} />);

    const status = await screen.findByLabelText("Eski Şirket durumu");
    expect(status.value).toBe("Başvuruldu");
    fireEvent.change(status, { target: { value: "Teknik mülakat" } });

    await waitFor(() => expect(api.request).toHaveBeenCalledWith("/opportunities/3", expect.objectContaining({
      method: "PATCH",
      body: JSON.stringify({ status: "Teknik mülakat" }),
    })));
    expect((await screen.findByRole("status")).textContent).toContain("Teknik mülakat");
    await waitFor(() => expect(api.requestPage).toHaveBeenCalledTimes(2));
  });

  it("shows a legacy status without offering it as a new choice", async () => {
    render(<CrmWorkspace api={createApi([legacyRecord])} token="test-token" view="opportunities" onNavigate={vi.fn()} />);

    const status = await screen.findByLabelText("Eski Şirket durumu");
    expect(status.value).toBe("mülakat bekliyor");
    expect(status.options[0].textContent).toBe("mülakat bekliyor (eski değer)");
    expect(status.options[0].disabled).toBe(true);
  });

  it("keeps the record and explains when the status update fails", async () => {
    const api = createApi([{ ...legacyRecord, status: "Başvuruldu" }]);
    api.request.mockRejectedValueOnce(new Error("network"));
    render(<CrmWorkspace api={api} token="test-token" view="opportunities" onNavigate={vi.fn()} />);

    fireEvent.change(await screen.findByLabelText("Eski Şirket durumu"), { target: { value: "Teklif" } });

    expect((await screen.findByRole("alert")).textContent).toContain("Başvuru durumu güncellenemedi");
    expect(screen.getByLabelText("Eski Şirket durumu").value).toBe("Başvuruldu");
  });
});

describe("server-side opportunity search", () => {
  const lastPath = (api) => api.requestPage.mock.calls.at(-1)[0];

  it("searches all opportunities on the server once typing stops", async () => {
    const api = createApi([{ ...legacyRecord, status: "Başvuruldu" }]);
    render(<CrmWorkspace api={api} token="test-token" view="opportunities" onNavigate={vi.fn()} />);

    fireEvent.change(await screen.findByLabelText("Başvurularda ara"), { target: { value: "  Trendyol " } });

    await waitFor(() => expect(lastPath(api)).toBe("/opportunities?q=Trendyol"));
    expect(api.requestPage.mock.calls.at(-1)[1]).toMatchObject({ offset: 0 });
    expect(screen.queryByText(/yalnızca bu sayfadaki/)).toBeNull();
  });

  it("filters by status and combines it with the search", async () => {
    const api = createApi([{ ...legacyRecord, status: "Teklif" }]);
    render(<CrmWorkspace api={api} token="test-token" view="opportunities" onNavigate={vi.fn()} />);

    fireEvent.change(await screen.findByLabelText("Durum filtresi"), { target: { value: "Teklif" } });
    await waitFor(() => expect(lastPath(api)).toBe("/opportunities?status=Teklif"));

    fireEvent.change(screen.getByLabelText("Başvurularda ara"), { target: { value: "eski" } });
    await waitFor(() => expect(lastPath(api)).toBe("/opportunities?q=eski&status=Teklif"));
  });

  it("offers to clear the search when nothing matches", async () => {
    const api = createApi([]);
    render(<CrmWorkspace api={api} token="test-token" view="opportunities" onNavigate={vi.fn()} />);

    fireEvent.change(await screen.findByLabelText("Durum filtresi"), { target: { value: "Reddedildi" } });
    fireEvent.click(await screen.findByRole("button", { name: "Aramayı temizle" }));

    await waitFor(() => expect(lastPath(api)).toBe("/opportunities"));
    expect(screen.getByLabelText("Durum filtresi").value).toBe("");
  });

  it("keeps page-only search for the other lists", async () => {
    const api = createApi([]);
    render(<CrmWorkspace api={api} token="test-token" view="contacts" onNavigate={vi.fn()} />);

    expect(await screen.findByLabelText("Bu sayfada ara")).toBeTruthy();
    expect(screen.queryByLabelText("Durum filtresi")).toBeNull();
  });
});

describe("opportunity detail navigation", () => {
  it("opens an opportunity's detail from the list and returns to a refreshed list", async () => {
    const api = createApi([{ ...legacyRecord, status: "Başvuruldu" }]);
    api.request.mockImplementation(async (path) => {
      if (path === "/opportunities/3/detail") {
        return { opportunity: { ...legacyRecord, status: "Başvuruldu" }, contacts: [], tasks: [], activities: [], skills: [] };
      }
      return {};
    });
    render(<CrmWorkspace api={api} token="test-token" view="opportunities" onNavigate={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Eski Şirket ayrıntıları" }));

    expect(await screen.findByRole("heading", { name: "Stajyer" })).toBeTruthy();
    expect(api.request).toHaveBeenCalledWith("/opportunities/3/detail", expect.anything());

    fireEvent.click(screen.getByRole("button", { name: "← Başvurulara dön" }));

    expect(await screen.findByRole("button", { name: "Eski Şirket ayrıntıları" })).toBeTruthy();
    await waitFor(() => expect(api.requestPage).toHaveBeenCalledTimes(2));
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

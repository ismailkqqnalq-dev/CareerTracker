import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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

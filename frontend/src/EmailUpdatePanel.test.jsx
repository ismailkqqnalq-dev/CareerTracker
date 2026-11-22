import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import EmailUpdatePanel from "./EmailUpdatePanel.jsx";

afterEach(cleanup);

const rejection = {
  type: "ret",
  confidence: 0.998,
  opportunity: { id: 7, company: "Trendyol", position: "Backend", status: "Teknik mülakat" },
  candidates: [],
  suggestion: { status: "Reddedildi", last_contact_date: "2026-11-22", task: null },
  explanation: "Bu, Trendyol başvurusu için olumsuz bir dönüş gibi görünüyor.",
};

function renderPanel(api, onApplied = vi.fn()) {
  render(<EmailUpdatePanel api={api} token="t" opportunityId={7} currentStatus="Teknik mülakat" onApplied={onApplied} />);
  return onApplied;
}

function analyze(text = "Maalesef başka bir adayla ilerleme kararı aldık.") {
  fireEvent.change(screen.getByLabelText("E-posta metni"), { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "E-postayı analiz et" }));
}

describe("email update panel", () => {
  it("analyzes a pasted email for this opportunity and shows the suggested changes", async () => {
    const api = { request: vi.fn(async () => rejection) };
    renderPanel(api);

    fireEvent.change(screen.getByLabelText("E-posta konusu (isteğe bağlı)"), { target: { value: "Başvurunuz hakkında" } });
    analyze();

    const changes = await screen.findByRole("list", { name: "Önerilen değişiklikler" });
    expect(within(changes).getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      "Durum: Teknik mülakat → Reddedildi",
      expect.stringContaining("Son temas tarihi"),
    ]);
    expect(screen.getByText("Olumsuz dönüş")).toBeTruthy();
    const [path, options] = api.request.mock.calls[0];
    expect(path).toBe("/email-insights/analyze");
    expect(JSON.parse(options.body)).toMatchObject({ subject: "Başvurunuz hakkında", opportunity_id: 7 });
  });

  it("applies the suggestion only after the user confirms", async () => {
    const api = { request: vi.fn(async (path) => (path === "/email-insights/analyze" ? rejection : {})) };
    const onApplied = renderPanel(api);

    analyze();
    fireEvent.click(await screen.findByRole("button", { name: "Önerileri uygula" }));

    await waitFor(() => expect(onApplied).toHaveBeenCalledWith("E-postadaki bilgiyle başvuru güncellendi."));
    const patch = api.request.mock.calls.find(([path]) => path === "/opportunities/7");
    expect(patch[1].method).toBe("PATCH");
    expect(JSON.parse(patch[1].body)).toEqual({ status: "Reddedildi", last_contact_date: "2026-11-22" });
    expect(screen.getByLabelText("E-posta metni").value).toBe("");
  });

  it("creates the suggested task for an assessment invitation", async () => {
    const assessment = {
      ...rejection,
      type: "degerlendirme",
      suggestion: { status: null, last_contact_date: null, task: { description: "Trendyol değerlendirmesini (test/ödev) tamamla", due_date: "2026-11-25" } },
    };
    const api = { request: vi.fn(async (path) => (path === "/email-insights/analyze" ? assessment : {})) };
    renderPanel(api);

    analyze("Online kodlama testini tamamlamanızı rica ederiz.");
    fireEvent.click(await screen.findByRole("button", { name: "Önerileri uygula" }));

    await waitFor(() => expect(api.request.mock.calls.some(([path]) => path === "/tasks")).toBe(true));
    const task = api.request.mock.calls.find(([path]) => path === "/tasks");
    expect(JSON.parse(task[1].body)).toEqual({ description: "Trendyol değerlendirmesini (test/ödev) tamamla", due_date: "2026-11-25", opportunity_id: 7 });
    expect(api.request.mock.calls.some(([path]) => path === "/opportunities/7")).toBe(false);
  });

  it("changes nothing when the user dismisses the suggestion", async () => {
    const api = { request: vi.fn(async () => rejection) };
    const onApplied = renderPanel(api);

    analyze();
    fireEvent.click(await screen.findByRole("button", { name: "Vazgeç" }));

    expect(screen.queryByRole("list", { name: "Önerilen değişiklikler" })).toBeNull();
    expect(api.request).toHaveBeenCalledTimes(1);
    expect(onApplied).not.toHaveBeenCalled();
  });

  it("offers no action for an unrelated email", async () => {
    const unrelated = { ...rejection, type: "diger", suggestion: { status: null, last_contact_date: null, task: null }, explanation: "Bu işe alımla ilgili görünmeyen bir e-posta." };
    const api = { request: vi.fn(async () => unrelated) };
    renderPanel(api);

    analyze("Bu haftanın öne çıkan ilanları");

    expect(await screen.findByText("İşe alımla ilgili değil")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Önerileri uygula" })).toBeNull();
  });

  it("explains a failed analysis", async () => {
    const api = { request: vi.fn().mockRejectedValue(Object.assign(new Error("down"), { status: 503 })) };
    renderPanel(api);

    analyze();

    expect((await screen.findByRole("alert")).textContent).toContain("E-posta analiz edilemedi");
  });
});

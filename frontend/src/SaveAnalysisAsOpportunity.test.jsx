import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import SaveAnalysisAsOpportunity from "./SaveAnalysisAsOpportunity.jsx";
import { ApiError } from "./api.js";

afterEach(cleanup);

const analysis = {
  role: "Backend Developer",
  metadata: {
    company: { value: "Örnek Teknoloji", line_number: 1 },
    location: { value: "İzmir", line_number: 3 },
    salary: { value: "₺50.000–₺70.000", line_number: 4 },
    work_arrangement: { value: "Hibrit", line_number: 5 },
    application_url: { value: "https://example.com/jobs/1", line_number: 6 },
  },
  skills: [
    { skill_id: 1, name: "Python", occurrences: [] },
    { skill_id: 2, name: "Docker", occurrences: [] },
  ],
  profile_match: null,
};

function renderForm({ result = analysis, request, onNavigate = vi.fn() } = {}) {
  const api = { request: request || vi.fn(async () => ({ id: 9, company: "Örnek Teknoloji", position: "Backend Developer" })) };
  render(<SaveAnalysisAsOpportunity result={result} api={api} token="test-token" onNavigate={onNavigate} />);
  fireEvent.click(screen.getByRole("button", { name: "Bu ilanı başvuru olarak kaydet" }));
  return { api, onNavigate };
}

describe("SaveAnalysisAsOpportunity", () => {
  it("starts collapsed so the analysis results stay uncluttered", () => {
    const api = { request: vi.fn() };
    render(<SaveAnalysisAsOpportunity result={analysis} api={api} token="test-token" />);

    expect(screen.queryByLabelText("Şirket")).toBeNull();
    expect(screen.getByRole("button", { name: "Bu ilanı başvuru olarak kaydet" })).toBeTruthy();
  });

  it("prefills the form from the analysis and keeps free-text salary in notes", () => {
    renderForm();

    expect(screen.getByLabelText("Şirket").value).toBe("Örnek Teknoloji");
    expect(screen.getByLabelText("Pozisyon").value).toBe("Backend Developer");
    expect(screen.getByLabelText("Konum").value).toBe("İzmir");
    expect(screen.getByLabelText("İlan bağlantısı").value).toBe("https://example.com/jobs/1");
    expect(screen.getByLabelText("Notlar").value).toBe("İlandaki ücret: ₺50.000–₺70.000\nÇalışma düzeni: Hibrit");
    expect(screen.getByLabelText("Python").checked).toBe(true);
    expect(screen.getByLabelText("Docker").checked).toBe(true);
  });

  it("does not prefill a non-http application link", () => {
    renderForm({
      result: { ...analysis, metadata: { ...analysis.metadata, application_url: { value: "javascript:alert(1)", line_number: 6 } } },
    });

    expect(screen.getByLabelText("İlan bağlantısı").value).toBe("");
  });

  it("creates the opportunity with only the checked skills and offers navigation", async () => {
    const { api, onNavigate } = renderForm();

    fireEvent.click(screen.getByLabelText("Docker"));
    fireEvent.click(screen.getByRole("button", { name: "Başvuru olarak kaydet" }));

    await screen.findByText(/başvurularına eklendi; 1 beceri bağlandı/);
    expect(api.request).toHaveBeenCalledTimes(1);
    const [path, options] = api.request.mock.calls[0];
    expect(path).toBe("/opportunities");
    expect(options.method).toBe("POST");
    const body = JSON.parse(options.body);
    expect(body).toMatchObject({
      company: "Örnek Teknoloji",
      position: "Backend Developer",
      type: "İş",
      status: "Başvuruldu",
      salary: 0,
      next_action: "",
      skill_ids: [1],
    });
    expect(body.application_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);

    fireEvent.click(screen.getByRole("button", { name: "Başvurulara git" }));
    expect(onNavigate).toHaveBeenCalledWith("opportunities");
  });

  it("explains an unknown skill error and keeps the form for another try", async () => {
    const request = vi.fn(async () => { throw new ApiError(404, "unknown_skill"); });
    renderForm({ request });

    fireEvent.click(screen.getByRole("button", { name: "Başvuru olarak kaydet" }));

    expect((await screen.findByRole("alert")).textContent).toContain("artık katalogda yok");
    await waitFor(() => expect(screen.getByRole("button", { name: "Başvuru olarak kaydet" }).disabled).toBe(false));
  });
});

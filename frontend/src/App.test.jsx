import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App.jsx";

function jsonResponse(status, body) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
  };
}

function setupLoggedInApp() {
  sessionStorage.setItem("careertracker_token", "temporary-test-token");
  const fetchMock = vi.fn(async (url) => {
    if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
    if (url.includes("/skills/suggestions?status=pending")) return jsonResponse(200, []);
    if (new URL(url, "http://localhost").pathname.endsWith("/skills")) return jsonResponse(200, []);
    throw new Error(`Unexpected request: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);
  return fetchMock;
}

function setupSuggestionReviewApp(patchResponse) {
  sessionStorage.setItem("careertracker_token", "temporary-test-token");
  let pending = true;
  const fetchMock = vi.fn(async (url, options = {}) => {
    if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
    if (url.includes("/skills/suggestions?status=pending")) {
      return jsonResponse(200, pending ? [{
        id: 2,
        raw_name: "Pyton",
        normalized_name: "pyton",
        status: "pending",
        created_at: "2026-10-25T00:00:00Z",
      }] : []);
    }
    if (new URL(url, "http://localhost").pathname.endsWith("/skills")) return jsonResponse(200, [{ id: 5, name: "Python", category: "language" }]);
    if (url.includes("/skills/suggestions/2/candidates")) {
      return jsonResponse(200, [{ id: 5, name: "Python", category: "language", score: 0.9 }]);
    }
    if (url.endsWith("/skills/suggestions/2") && options.method === "PATCH") {
      const result = await patchResponse();
      if (result.ok && result.body?.status === "accepted") pending = false;
      return jsonResponse(result.status, result.body);
    }
    throw new Error(`Unexpected request: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);
  return fetchMock;
}

function deferred() {
  let resolve;
  const promise = new Promise((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
}

describe("skill suggestion input", () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("uses response status to show that a pending suggestion was queued", async () => {
    const fetchMock = setupLoggedInApp();
    fetchMock.mockImplementation(async (url, options = {}) => {
      if (url.endsWith("/skills/suggestions") && options.method === "POST") {
        return jsonResponse(200, { id: 8, raw_name: "Rust", status: "pending", resolved_skill_id: null });
      }
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
      if (url.includes("/skills/suggestions?status=pending")) return jsonResponse(200, []);
      if (new URL(url, "http://localhost").pathname.endsWith("/skills")) return jsonResponse(200, []);
      throw new Error(`Unexpected request: ${url}`);
    });

    fireEvent.change(await screen.findByLabelText("Beceri adı"), { target: { value: "Rust" } });
    fireEvent.click(screen.getByRole("button", { name: "Öneri gönder" }));

    expect((await screen.findByRole("status")).textContent).toContain("bekleyen önerilere eklendi");
  });

  it("shows a distinct message for accepted suggestions whose target was deleted", async () => {
    const fetchMock = setupLoggedInApp();
    fetchMock.mockImplementation(async (url, options = {}) => {
      if (url.endsWith("/skills/suggestions") && options.method === "POST") {
        return jsonResponse(200, { id: 9, raw_name: "Old variant", status: "accepted", resolved_skill_id: null });
      }
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
      if (url.includes("/skills/suggestions?status=pending")) return jsonResponse(200, []);
      if (new URL(url, "http://localhost").pathname.endsWith("/skills")) return jsonResponse(200, []);
      throw new Error(`Unexpected request: ${url}`);
    });

    fireEvent.change(await screen.findByLabelText("Beceri adı"), { target: { value: "Old variant" } });
    fireEvent.click(screen.getByRole("button", { name: "Öneri gönder" }));

    expect((await screen.findByRole("status")).textContent).toContain("daha önce kabul edilmiş");
    expect(screen.getByRole("status").textContent).toContain("hedef beceri artık mevcut değil");
  });

  it("shows a separate message for an accepted suggestion with an existing target", async () => {
    const fetchMock = setupLoggedInApp();
    fetchMock.mockImplementation(async (url, options = {}) => {
      if (url.endsWith("/skills/suggestions") && options.method === "POST") {
        return jsonResponse(200, { id: 10, raw_name: "PyTorch", status: "accepted", resolved_skill_id: 4 });
      }
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
      if (url.includes("/skills/suggestions?status=pending")) return jsonResponse(200, []);
      if (new URL(url, "http://localhost").pathname.endsWith("/skills")) return jsonResponse(200, []);
      throw new Error(`Unexpected request: ${url}`);
    });

    fireEvent.change(await screen.findByLabelText("Beceri adı"), { target: { value: "PyTorch" } });
    fireEvent.click(screen.getByRole("button", { name: "Öneri gönder" }));

    expect((await screen.findByRole("status")).textContent).toContain("daha önce kabul edilmiş ve eşleştirilmiş");
    expect(screen.getByRole("status").textContent).not.toContain("hedef beceri artık mevcut değil");
  });

  it("resolves a recognized skill and shows its canonical catalog name", async () => {
    const fetchMock = setupLoggedInApp();
    fetchMock.mockImplementation(async (url, options = {}) => {
      if (url.endsWith("/skills/suggestions") && options.method === "POST") {
        return jsonResponse(409, {
          detail: "backend wording is not a UI contract",
          error_code: "skill_already_recognized",
        });
      }
      if (url.endsWith("/skills/resolve?name=Python")) {
        return jsonResponse(200, { id: 5, name: "Python", category: "language" });
      }
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
      if (url.includes("/skills/suggestions?status=pending")) return jsonResponse(200, []);
      if (new URL(url, "http://localhost").pathname.endsWith("/skills")) return jsonResponse(200, []);
      throw new Error(`Unexpected request: ${url}`);
    });

    fireEvent.change(await screen.findByLabelText("Beceri adı"), { target: { value: "Python" } });
    fireEvent.click(screen.getByRole("button", { name: "Öneri gönder" }));

    expect((await screen.findByRole("alert")).textContent).toContain('"Python" olarak tanınıyor');
    expect(fetchMock).toHaveBeenCalledWith("/api/skills/resolve?name=Python", expect.anything());
    expect(screen.queryByText("backend wording is not a UI contract")).toBeNull();
  });

  it("keeps the generic recognized-skill message when catalog resolution fails", async () => {
    const fetchMock = setupLoggedInApp();
    fetchMock.mockImplementation(async (url, options = {}) => {
      if (url.endsWith("/skills/suggestions") && options.method === "POST") {
        return jsonResponse(409, { error_code: "skill_already_recognized" });
      }
      if (url.endsWith("/skills/resolve?name=Python")) {
        return jsonResponse(404, { detail: "do not show backend detail" });
      }
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
      if (url.includes("/skills/suggestions?status=pending")) return jsonResponse(200, []);
      if (new URL(url, "http://localhost").pathname.endsWith("/skills")) return jsonResponse(200, []);
      throw new Error(`Unexpected request: ${url}`);
    });

    fireEvent.change(await screen.findByLabelText("Beceri adı"), { target: { value: "Python" } });
    fireEvent.click(screen.getByRole("button", { name: "Öneri gönder" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Bu beceri zaten katalogda tanınıyor");
    expect(screen.queryByText("do not show backend detail")).toBeNull();
  });

  it("uses centralized 401 handling if resolving a recognized skill returns unauthorized", async () => {
    const fetchMock = setupLoggedInApp();
    fetchMock.mockImplementation(async (url, options = {}) => {
      if (url.endsWith("/skills/suggestions") && options.method === "POST") {
        return jsonResponse(409, { error_code: "skill_already_recognized" });
      }
      if (url.endsWith("/skills/resolve?name=Python")) {
        return jsonResponse(401, { detail: "private auth detail" });
      }
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
      if (url.includes("/skills/suggestions?status=pending")) return jsonResponse(200, []);
      if (new URL(url, "http://localhost").pathname.endsWith("/skills")) return jsonResponse(200, []);
      throw new Error(`Unexpected request: ${url}`);
    });

    fireEvent.change(await screen.findByLabelText("Beceri adı"), { target: { value: "Python" } });
    fireEvent.click(screen.getByRole("button", { name: "Öneri gönder" }));

    expect(await screen.findByRole("heading", { name: "Hesabına giriş yap" })).toBeTruthy();
    expect(sessionStorage.getItem("careertracker_token")).toBeNull();
    expect(screen.queryByText("private auth detail")).toBeNull();
  });

  it("shows mapping success and removes the accepted suggestion from the pending list", async () => {
    const fetchMock = setupSuggestionReviewApp(async () => ({
      status: 200,
      ok: true,
      body: { id: 2, raw_name: "Pyton", status: "accepted", resolved_skill_id: 5 },
    }));

    fireEvent.click(await screen.findByRole("button", { name: /Python/ }));
    fireEvent.click(screen.getByRole("button", { name: "Eşleştirmeyi onayla" }));

    expect((await screen.findByRole("status")).textContent).toContain("Pyton” becerisi eşleştirildi");
    await waitFor(() => expect(screen.queryByText("Pyton")).toBeNull());
    expect(fetchMock.mock.calls.some(([url, options]) => url.endsWith("/skills/suggestions/2") && options?.method === "PATCH")).toBe(true);
  });

  it("shows an error and retains the suggestion if mapping response status is not accepted", async () => {
    setupSuggestionReviewApp(async () => ({
      status: 200,
      ok: true,
      body: { id: 2, raw_name: "Pyton", status: "pending", resolved_skill_id: null },
    }));

    fireEvent.click(await screen.findByRole("button", { name: /Python/ }));
    fireEvent.click(screen.getByRole("button", { name: "Eşleştirmeyi onayla" }));

    expect((await screen.findByRole("alert")).textContent).toContain("beklenen durumu döndürmedi");
    expect(screen.getByText("Pyton")).toBeTruthy();
  });

  it("shows a request error if mapping fails with a non-401 response", async () => {
    setupSuggestionReviewApp(async () => ({
      status: 503,
      ok: false,
      body: { detail: "private mapping failure" },
    }));

    fireEvent.click(await screen.findByRole("button", { name: /Python/ }));
    fireEvent.click(screen.getByRole("button", { name: "Eşleştirmeyi onayla" }));

    expect((await screen.findByRole("alert")).textContent).toContain("İstek tamamlanamadı");
    expect(screen.queryByText("private mapping failure")).toBeNull();
    expect(screen.getByText("Pyton")).toBeTruthy();
  });

  it("locks the submit button during a request and does not send twice", async () => {
    const fetchMock = setupLoggedInApp();
    const request = deferred();
    fetchMock.mockImplementation(async (url, options = {}) => {
      if (url.endsWith("/skills/suggestions") && options.method === "POST") return request.promise;
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
      if (url.includes("/skills/suggestions?status=pending")) return jsonResponse(200, []);
      if (new URL(url, "http://localhost").pathname.endsWith("/skills")) return jsonResponse(200, []);
      throw new Error(`Unexpected request: ${url}`);
    });
    fireEvent.change(await screen.findByLabelText("Beceri adı"), { target: { value: "Rust" } });
    fireEvent.click(screen.getByRole("button", { name: "Öneri gönder" }));

    const sendingButton = await screen.findByRole("button", { name: "Gönderiliyor…" });
    expect(sendingButton.disabled).toBe(true);
    fireEvent.click(sendingButton);
    expect(fetchMock.mock.calls.filter(([url, options]) => url.endsWith("/skills/suggestions") && options?.method === "POST")).toHaveLength(1);

    request.resolve(jsonResponse(200, { id: 11, raw_name: "Rust", status: "pending", resolved_skill_id: null }));
    expect((await screen.findByRole("status")).textContent).toContain("bekleyen önerilere eklendi");
  });

  it("does not send a blank or whitespace-only skill name", async () => {
    const fetchMock = setupLoggedInApp();
    const field = await screen.findByLabelText("Beceri adı");
    const submitButton = screen.getByRole("button", { name: "Öneri gönder" });
    expect(submitButton.disabled).toBe(true);

    fireEvent.change(field, { target: { value: "   " } });
    expect(submitButton.disabled).toBe(true);
    fireEvent.submit(field.closest("form"));

    expect(fetchMock.mock.calls.some(([url, options]) => url.endsWith("/skills/suggestions") && options?.method === "POST")).toBe(false);
  });

  it("shows a helpful error instead of crashing when the network request rejects", async () => {
    sessionStorage.setItem("careertracker_token", "temporary-test-token");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(<App />);

    expect((await screen.findByRole("alert")).textContent).toContain("İstek tamamlanamadı");
    expect(screen.getByRole("heading", { name: "Beceri önerileri" })).toBeTruthy();
    expect(screen.getByLabelText("Beceri adı")).toBeTruthy();
  });

});

describe("job text analysis", () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows rule-based skill matches returned by the authenticated API", async () => {
    const fetchMock = setupLoggedInApp();
    fetchMock.mockImplementation(async (url) => {
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
      if (url.includes("/skills/suggestions?status=pending")) return jsonResponse(200, []);
      if (new URL(url, "http://localhost").pathname.endsWith("/skills")) return jsonResponse(200, []);
      if (url.endsWith("/job-analysis")) {
        return jsonResponse(200, {
          role: "Backend Engineer",
          skills: [{
            skill_id: 7,
            name: "Python",
            category: "language",
            occurrences: [{ line_number: 2, matched_text: "Python", section: "required" }],
          }],
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    fireEvent.change(await screen.findByLabelText("İlan metni"), {
      target: { value: "Pozisyon: Backend Engineer\nPython" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Metni analiz et" }));

    expect(await screen.findByRole("heading", { name: "Bulunan beceriler" })).toBeTruthy();
    expect(screen.getByText("Backend Engineer")).toBeTruthy();
    expect(screen.getByText("Python")).toBeTruthy();
    expect(screen.getByText("Programlama dili")).toBeTruthy();
    expect(screen.getByText("Zorunlu bölüm · satır 2")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith("/api/job-analysis", expect.objectContaining({
      method: "POST",
      headers: expect.any(Headers),
    }));
  });

  it("shows explicitly labeled posting details and compares detected skills with the user's profile", async () => {
    const fetchMock = setupLoggedInApp();
    fetchMock.mockImplementation(async (url) => {
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
      if (url.includes("/skills/suggestions?status=pending")) return jsonResponse(200, []);
      if (new URL(url, "http://localhost").pathname.endsWith("/skills")) return jsonResponse(200, []);
      if (url.endsWith("/job-analysis")) {
        return jsonResponse(200, {
          role: "Backend Engineer",
          role_line_number: 1,
          metadata: {
            company: { value: "Örnek AŞ", line_number: 2 },
            location: { value: "İstanbul", line_number: 3 },
            employment_type: { value: "Tam zamanlı", line_number: 4 },
            work_arrangement: { value: "Hibrit", line_number: 5 },
            salary: { value: "80.000 TL", line_number: 6 },
            experience: { value: "3 yıl", line_number: 7 },
            education: { value: "Lisans", line_number: 8 },
            application_url: { value: "https://example.test/jobs/1", line_number: 9 },
          },
          skills: [
            {
              skill_id: 7,
              name: "Python",
              category: "language",
              profile_status: "in_profile",
              profile_proficiency_level: "advanced",
              profile_years_experience: 3.5,
              occurrences: [{ line_number: 11, matched_text: "Python", section: "required" }],
            },
            {
              skill_id: 8,
              name: "Kubernetes",
              category: "tool",
              profile_status: "missing",
              profile_proficiency_level: null,
              profile_years_experience: null,
              occurrences: [{ line_number: 14, matched_text: "Kubernetes", section: "preferred" }],
            },
          ],
          profile_match: {
            required: { total_count: 1, matched_count: 1, match_percentage: 100, missing_skills: [] },
            preferred: { total_count: 1, matched_count: 0, match_percentage: 0, missing_skills: ["Kubernetes"] },
            unspecified: { total_count: 0, matched_count: 0, match_percentage: null, missing_skills: [] },
          },
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    fireEvent.change(await screen.findByLabelText("İlan metni"), {
      target: { value: "Pozisyon: Backend Engineer\nŞirket: Örnek AŞ\nPython" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Metni analiz et" }));

    expect(await screen.findByRole("heading", { name: "Bulunan beceriler" })).toBeTruthy();
    expect(screen.getByText("Şirket")).toBeTruthy();
    expect(screen.getByText("Örnek AŞ")).toBeTruthy();
    expect(screen.getByText("Konum")).toBeTruthy();
    expect(screen.getByText("İstanbul")).toBeTruthy();
    expect(screen.getByText("Tam zamanlı")).toBeTruthy();
    expect(screen.getByText("Hibrit")).toBeTruthy();
    expect(screen.getByText("80.000 TL")).toBeTruthy();
    expect(screen.getByText("3 yıl")).toBeTruthy();
    expect(screen.getByText("Lisans")).toBeTruthy();
    expect(screen.getByText("https://example.test/jobs/1")).toBeTruthy();
    expect(screen.getByText("Satır 2")).toBeTruthy();
    expect(screen.getByText(/Profilinde kayıtlı.*İleri.*3,5 yıl/)).toBeTruthy();
    expect(screen.getByText(/Profilinde kayıtlı değil/)).toBeTruthy();
    const requiredSummary = screen.getByText("Zorunlu beceriler").closest("li").textContent;
    expect(requiredSummary).toContain("1 / 1");
    expect(requiredSummary).toContain("%100 profilde kayıtlı");
    const preferredSummary = screen.getByText("Tercih edilen beceriler").closest("li").textContent;
    expect(preferredSummary).toContain("0 / 1");
    expect(preferredSummary).toContain("%0 profilde kayıtlı");
    expect(screen.getByText(/iş için uygunluk veya başarı olasılığı değildir/i)).toBeTruthy();
    expect(screen.getByText(/katalog dışındaki beceriler görünmeyebilir/i)).toBeTruthy();
    expect(screen.queryByRole("link", { name: "https://example.test/jobs/1" })).toBeNull();
  });

  it("explains when the job text is larger than the API limit", async () => {
    const fetchMock = setupLoggedInApp();
    fetchMock.mockImplementation(async (url) => {
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
      if (url.includes("/skills/suggestions?status=pending")) return jsonResponse(200, []);
      if (new URL(url, "http://localhost").pathname.endsWith("/skills")) return jsonResponse(200, []);
      if (url.endsWith("/job-analysis")) return jsonResponse(413, {
        detail: "Job text exceeds the 100 KB limit.",
        error_code: "job_text_too_large",
      });
      throw new Error(`Unexpected request: ${url}`);
    });

    fireEvent.change(await screen.findByLabelText("İlan metni"), {
      target: { value: "Long job description" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Metni analiz et" }));

    expect((await screen.findByRole("alert")).textContent).toContain("100 KB");
  });
});

describe("OCR image upload", () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("extracts image text and lets the user send it to job analysis", async () => {
    const fetchMock = setupLoggedInApp();
    fetchMock.mockImplementation(async (url, options = {}) => {
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
      if (url.includes("/skills/suggestions?status=pending")) return jsonResponse(200, []);
      if (new URL(url, "http://localhost").pathname.endsWith("/skills")) return jsonResponse(200, []);
      if (url.endsWith("/ocr/extract")) {
        return jsonResponse(200, {
          text: "Pozisyon: Backend Engineer\nPython ve FastAPI",
          width: 1200,
          height: 800,
          image_format: "PNG",
        });
      }
      if (url.endsWith("/job-analysis")) {
        return jsonResponse(200, {
          role: "Backend Engineer",
          skills: [{
            skill_id: 7,
            name: "Python",
            category: "language",
            occurrences: [{ line_number: 2, matched_text: "Python", section: "unspecified" }],
          }],
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    const file = new File([new Uint8Array([1, 2, 3])], "posting.png", { type: "image/png" });
    fireEvent.change(await screen.findByLabelText("İlan görseli"), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Görselden metin çıkar" }));

    const extractedText = await screen.findByLabelText("Çıkarılan metin");
    expect(extractedText.value).toContain("Python ve FastAPI");
    expect(fetchMock).toHaveBeenCalledWith("/api/ocr/extract", expect.objectContaining({
      method: "POST",
      body: file,
      headers: expect.any(Headers),
    }));
    const [, ocrOptions] = fetchMock.mock.calls.find(([url]) => url.endsWith("/ocr/extract"));
    expect(ocrOptions.headers.get("Content-Type")).toBe("image/png");
    expect(ocrOptions.headers.get("Authorization")).toBe("Bearer temporary-test-token");

    fireEvent.click(screen.getByRole("button", { name: "Analiz alanına aktar" }));
    const jobText = screen.getByLabelText("İlan metni");
    expect(jobText.value).toBe(extractedText.value);
    fireEvent.click(screen.getByRole("button", { name: "Metni analiz et" }));
    expect(await screen.findByRole("heading", { name: "Bulunan beceriler" })).toBeTruthy();
    expect(screen.getByText("Python")).toBeTruthy();
  });

  it("rejects a non-PNG/JPEG file before sending a request", async () => {
    const fetchMock = setupLoggedInApp();
    const file = new File([new Uint8Array([1, 2, 3])], "posting.gif", { type: "image/gif" });

    fireEvent.change(await screen.findByLabelText("İlan görseli"), {
      target: { files: [file] },
    });

    expect((await screen.findByRole("alert")).textContent).toContain("PNG veya JPEG");
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith("/ocr/extract"))).toBe(false);
  });

  it("rejects a file over 10 MiB before sending it", async () => {
    const fetchMock = setupLoggedInApp();
    const file = new File([new Uint8Array(10 * 1024 * 1024 + 1)], "posting.png", { type: "image/png" });

    fireEvent.change(await screen.findByLabelText("İlan görseli"), {
      target: { files: [file] },
    });

    expect((await screen.findByRole("alert")).textContent).toContain("10 MiB");
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith("/ocr/extract"))).toBe(false);
  });

  it("uses the shared login flow when the OCR request returns 401", async () => {
    const fetchMock = setupLoggedInApp();
    fetchMock.mockImplementation(async (url) => {
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
      if (url.includes("/skills/suggestions?status=pending")) return jsonResponse(200, []);
      if (new URL(url, "http://localhost").pathname.endsWith("/skills")) return jsonResponse(200, []);
      if (url.endsWith("/ocr/extract")) return jsonResponse(401, { detail: "expired" });
      throw new Error(`Unexpected request: ${url}`);
    });

    const file = new File([new Uint8Array([1])], "posting.png", { type: "image/png" });
    fireEvent.change(await screen.findByLabelText("İlan görseli"), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Görselden metin çıkar" }));

    expect(await screen.findByRole("heading", { name: "Hesabına giriş yap" })).toBeTruthy();
    expect(sessionStorage.getItem("careertracker_token")).toBeNull();
  });
});

describe("profile and opportunity matching navigation", () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("opens the profile and matching panel and loads only the signed-in user's data", async () => {
    const fetchMock = setupLoggedInApp();
    fetchMock.mockImplementation(async (url) => {
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
      if (url.includes("/skills/suggestions?status=pending")) return jsonResponse(200, []);
      if (new URL(url, "http://localhost").pathname.endsWith("/skills")) {
        return jsonResponse(200, [{ id: 1, name: "Python", category: "language" }]);
      }
      if (url.includes("/users/me/skills?")) return jsonResponse(200, []);
      if (url.includes("/opportunities?")) {
        return jsonResponse(200, [{ id: 17, company: "Örnek AŞ", position: "Backend Developer" }]);
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    fireEvent.click(screen.getByRole("button", { name: "Profil ve eşleşme" }));

    expect(await screen.findByRole("heading", { name: "Profil becerilerim" })).toBeTruthy();
    expect(screen.getByRole("option", { name: /#17 · Örnek AŞ/ })).toBeTruthy();
    expect(fetchMock.mock.calls.some(([url]) => url.includes("/users/me/skills?limit=200"))).toBe(true);
    expect(fetchMock.mock.calls.some(([url]) => url.includes("/opportunities?limit=200"))).toBe(true);
  });
});

describe("application analytics navigation", () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("opens the monthly application analytics panel for the signed-in user", async () => {
    sessionStorage.setItem("careertracker_token", "temporary-test-token");
    const fetchMock = vi.fn(async (url) => {
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
      if (url.includes("/skills/suggestions?status=pending")) return jsonResponse(200, []);
      if (new URL(url, "http://localhost").pathname.endsWith("/skills")) return jsonResponse(200, []);
      if (url.includes("/analytics/applications?months=12")) {
        return jsonResponse(200, {
          months: 12,
          start_month: "2026-01",
          end_month: "2026-12",
          total_applications: 1,
          applications_by_month: [{ month: "2026-12", count: 1 }],
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Başvuru analizi" }));

    expect(await screen.findByRole("heading", { name: "Aylık başvurular" })).toBeTruthy();
    expect(await screen.findByRole("listitem", { name: "2026-12: 1 başvuru" })).toBeTruthy();
    expect(fetchMock.mock.calls.some(([url]) => url.includes("/analytics/applications?months=12"))).toBe(true);
  });

  it("uses the shared logout flow when analytics returns 401", async () => {
    sessionStorage.setItem("careertracker_token", "temporary-test-token");
    const fetchMock = vi.fn(async (url) => {
      if (url.endsWith("/auth/me")) return jsonResponse(200, { email: "test@example.com" });
      if (url.includes("/skills/suggestions?status=pending")) return jsonResponse(200, []);
      if (new URL(url, "http://localhost").pathname.endsWith("/skills")) return jsonResponse(200, []);
      if (url.includes("/analytics/applications?months=12")) return jsonResponse(401, { detail: "expired" });
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Başvuru analizi" }));

    expect(await screen.findByRole("heading", { name: "Hesabına giriş yap" })).toBeTruthy();
    expect(sessionStorage.getItem("careertracker_token")).toBeNull();
  });
});

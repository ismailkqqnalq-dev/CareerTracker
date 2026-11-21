import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import AssistantPanel from "./AssistantPanel.jsx";

afterEach(cleanup);

const statusReply = {
  intent: "basvuru_durumu",
  confidence: 0.9987,
  reply: "Başvurunun son durumu:",
  items: [{ title: "Trendyol · Backend", details: ["Durum: Teknik mülakat", "Son temas: 12 gün önce"] }],
  suggestions: [],
};

function ask(text) {
  fireEvent.change(screen.getByLabelText("Sorun"), { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "Sor" }));
}

describe("assistant panel", () => {
  it("sends the question and shows the reply with the detected intent", async () => {
    const api = { request: vi.fn(async () => statusReply) };
    render(<AssistantPanel api={api} token="test-token" />);

    ask("Trendyol başvurum ne alemde");

    expect(await screen.findByText("Trendyol · Backend")).toBeTruthy();
    expect(screen.getByText("Durum: Teknik mülakat")).toBeTruthy();
    expect(screen.getByText("Anlaşılan: Başvuru durumu · güven %100")).toBeTruthy();
    const [path, options] = api.request.mock.calls[0];
    expect(path).toBe("/assistant/ask");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body).message).toBe("Trendyol başvurum ne alemde");
    expect(JSON.parse(options.body).today).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(screen.getByLabelText("Sorun").value).toBe("");
  });

  it("asks a starter question with one click and then hides the starters", async () => {
    const api = { request: vi.fn(async () => ({ ...statusReply, intent: "bugun_ne_var", items: [], reply: "Açık görevin yok." })) };
    render(<AssistantPanel api={api} token="test-token" />);

    fireEvent.click(screen.getByRole("button", { name: "Bugün ne yapmalıyım?" }));

    expect(await screen.findByText("Açık görevin yok.")).toBeTruthy();
    expect(JSON.parse(api.request.mock.calls[0][1].body).message).toBe("Bugün ne yapmalıyım?");
    expect(screen.queryByLabelText("Örnek sorular")).toBeNull();
  });

  it("sends a suggestion from a reply as the next question", async () => {
    const api = {
      request: vi.fn()
        .mockResolvedValueOnce({ intent: "anlasilamadi", confidence: 0.4, reply: "Bunu anlayamadım.", items: [], suggestions: ["Kaç başvurum var?"] })
        .mockResolvedValueOnce({ intent: "genel_durum", confidence: 0.99, reply: "Toplam 3 başvurun var.", items: [], suggestions: [] }),
    };
    render(<AssistantPanel api={api} token="test-token" />);

    ask("hava nasıl");
    fireEvent.click(await screen.findByRole("button", { name: "Kaç başvurum var?" }));

    expect(await screen.findByText("Toplam 3 başvurun var.")).toBeTruthy();
    expect(JSON.parse(api.request.mock.calls[1][1].body).message).toBe("Kaç başvurum var?");
  });

  it("keeps the question and explains when the request fails", async () => {
    const api = { request: vi.fn().mockRejectedValue(Object.assign(new Error("down"), { status: 503 })) };
    render(<AssistantPanel api={api} token="test-token" />);

    ask("Kimden ses çıkmadı");

    expect((await screen.findByRole("alert")).textContent).toContain("Asistan şu anda cevap veremedi");
    expect(screen.getByText("Kimden ses çıkmadı")).toBeTruthy();
    await waitFor(() => expect(screen.getByLabelText("Sorun").disabled).toBe(false));
  });

  it("does not send a blank question", () => {
    const api = { request: vi.fn() };
    render(<AssistantPanel api={api} token="test-token" />);

    fireEvent.change(screen.getByLabelText("Sorun"), { target: { value: "   " } });

    expect(screen.getByRole("button", { name: "Sor" }).disabled).toBe(true);
    fireEvent.submit(screen.getByLabelText("Sorun").closest("form"));
    expect(api.request).not.toHaveBeenCalled();
  });
});

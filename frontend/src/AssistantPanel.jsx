import { useState } from "react";

const MAX_MESSAGE_LENGTH = 500;
const STARTER_QUESTIONS = [
  "Bugün ne yapmalıyım?",
  "Kimden ses çıkmadı?",
  "Hangi becerileri geliştirmeliyim?",
  "Kaç başvurum var?",
];
const INTENT_LABELS = {
  basvuru_durumu: "Başvuru durumu",
  bugun_ne_var: "Bugünün işleri",
  takip_gereken: "Takip edilmesi gerekenler",
  beceri_acigi: "Beceri açığı",
  genel_durum: "Genel durum",
  yardim: "Yardım",
  anlasilamadi: "Anlaşılamadı",
};

function localToday() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

function AssistantMessage({ message, onAsk, busy }) {
  if (message.role === "user") {
    return <li className="assistant-message from-user"><p>{message.text}</p></li>;
  }
  return (
    <li className="assistant-message from-assistant">
      <p>{message.reply}</p>
      {message.items.length > 0 && (
        <ul className="assistant-items">
          {message.items.map((item, index) => (
            <li key={`${item.title}-${index}`}>
              <strong>{item.title}</strong>
              {item.details.map((detail) => <span key={detail}>{detail}</span>)}
            </li>
          ))}
        </ul>
      )}
      {message.suggestions.length > 0 && (
        <div className="assistant-suggestions">
          {message.suggestions.map((suggestion) => (
            <button key={suggestion} type="button" className="button button-quiet" disabled={busy} onClick={() => onAsk(suggestion)}>{suggestion}</button>
          ))}
        </div>
      )}
      <small className="assistant-intent">
        Anlaşılan: {INTENT_LABELS[message.intent] || message.intent} · güven %{Math.round(message.confidence * 100)}
      </small>
    </li>
  );
}

export default function AssistantPanel({ api, token }) {
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function ask(text) {
    const message = text.trim();
    if (!message || busy) return;
    setBusy(true);
    setError("");
    setDraft("");
    setMessages((current) => [...current, { role: "user", text: message }]);
    try {
      const reply = await api.request("/assistant/ask", {
        method: "POST",
        token,
        body: JSON.stringify({ message, today: localToday() }),
      });
      setMessages((current) => [...current, { role: "assistant", ...reply }]);
    } catch (askError) {
      if (askError.status !== 401) setError("Asistan şu anda cevap veremedi. Biraz sonra tekrar dene.");
    } finally {
      setBusy(false);
    }
  }

  function submit(event) {
    event.preventDefault();
    ask(draft);
  }

  return (
    <section className="assistant-panel" aria-labelledby="assistant-title">
      <h2 id="assistant-title">Asistana sor</h2>
      <p className="muted">
        Soruların kayıtlarından cevaplanır; mesajların saklanmaz ve hiçbir dış servise gönderilmez.
      </p>

      {messages.length === 0 && (
        <div className="assistant-suggestions" aria-label="Örnek sorular">
          {STARTER_QUESTIONS.map((question) => (
            <button key={question} type="button" className="button button-quiet" onClick={() => ask(question)}>{question}</button>
          ))}
        </div>
      )}

      <ol className="assistant-log" role="log" aria-live="polite" aria-label="Asistan konuşması">
        {messages.map((message, index) => (
          <AssistantMessage key={index} message={message} onAsk={ask} busy={busy} />
        ))}
      </ol>

      {error && <p className="form-error" role="alert">{error}</p>}

      <form className="assistant-form" onSubmit={submit}>
        <label htmlFor="assistant-input">Sorun</label>
        <input
          id="assistant-input"
          type="text"
          maxLength={MAX_MESSAGE_LENGTH}
          placeholder="Örnek: Trendyol başvurum ne alemde?"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        />
        <button className="button button-primary" disabled={busy || !draft.trim()}>{busy ? "Düşünüyor…" : "Sor"}</button>
      </form>
    </section>
  );
}

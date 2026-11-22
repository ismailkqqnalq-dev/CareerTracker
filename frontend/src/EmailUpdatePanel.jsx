import { useState } from "react";
import { displayDate, today } from "./crmUtils.js";

const MAX_BODY_LENGTH = 20000;
const TYPE_LABELS = {
  basvuru_alindi: "Başvuru alındı bildirimi",
  mulakat_daveti: "Mülakat daveti",
  degerlendirme: "Test / ödev daveti",
  teklif: "İş teklifi",
  ret: "Olumsuz dönüş",
  diger: "İşe alımla ilgili değil",
};

function changesOf(suggestion, currentStatus) {
  const changes = [];
  if (suggestion.status) changes.push(`Durum: ${currentStatus || "Durum yok"} → ${suggestion.status}`);
  if (suggestion.last_contact_date) changes.push(`Son temas tarihi: ${displayDate(suggestion.last_contact_date)}`);
  if (suggestion.task) changes.push(`Yeni görev: ${suggestion.task.description} (son tarih ${displayDate(suggestion.task.due_date)})`);
  return changes;
}

export default function EmailUpdatePanel({ api, token, opportunityId, currentStatus, onApplied }) {
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function analyze(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await api.request("/email-insights/analyze", {
        method: "POST",
        token,
        body: JSON.stringify({ subject, body, opportunity_id: opportunityId, today: today() }),
      }));
    } catch (analyzeError) {
      if (analyzeError.status !== 401) setError("E-posta analiz edilemedi. Tekrar dene.");
    } finally {
      setBusy(false);
    }
  }

  async function apply() {
    const { suggestion } = result;
    setBusy(true);
    setError("");
    try {
      const update = {};
      if (suggestion.status) update.status = suggestion.status;
      if (suggestion.last_contact_date) update.last_contact_date = suggestion.last_contact_date;
      if (Object.keys(update).length) {
        await api.request(`/opportunities/${opportunityId}`, { method: "PATCH", token, body: JSON.stringify(update) });
      }
      if (suggestion.task) {
        await api.request("/tasks", {
          method: "POST",
          token,
          body: JSON.stringify({ ...suggestion.task, opportunity_id: opportunityId }),
        });
      }
      setSubject("");
      setBody("");
      setResult(null);
      onApplied("E-postadaki bilgiyle başvuru güncellendi.");
    } catch (applyError) {
      if (applyError.status !== 401) setError("Öneriler uygulanamadı. Tekrar dene.");
    } finally {
      setBusy(false);
    }
  }

  const changes = result ? changesOf(result.suggestion, currentStatus) : [];

  return (
    <section className="email-update" aria-labelledby="email-update-title">
      <h3 id="email-update-title">E-postadan güncelle</h3>
      <p className="muted">Şirketten gelen e-postayı yapıştır; ne olduğunu anlayıp önerilen değişiklikleri gösteririm. Sen onaylamadan hiçbir şey değişmez ve e-posta saklanmaz.</p>
      <form className="detail-quick-form" onSubmit={analyze} aria-label="E-postayı analiz et">
        <label htmlFor="email-update-subject">E-posta konusu (isteğe bağlı)</label>
        <input id="email-update-subject" maxLength={500} value={subject} onChange={(event) => setSubject(event.target.value)} />
        <label htmlFor="email-update-body">E-posta metni</label>
        <textarea id="email-update-body" rows={5} maxLength={MAX_BODY_LENGTH} value={body} onChange={(event) => setBody(event.target.value)} />
        <button className="button button-primary" disabled={busy || !body.trim()}>{busy && !result ? "Analiz ediliyor…" : "E-postayı analiz et"}</button>
      </form>

      {error && <p className="form-error" role="alert">{error}</p>}

      {result && (
        <div className="email-update-result" aria-live="polite">
          <p><strong>{TYPE_LABELS[result.type] || result.type}</strong> · güven %{Math.round(result.confidence * 100)}</p>
          <p>{result.explanation}</p>
          {changes.length > 0 ? (
            <>
              <ul aria-label="Önerilen değişiklikler">{changes.map((change) => <li key={change}>{change}</li>)}</ul>
              <div className="detail-actions">
                <button type="button" className="button button-primary" disabled={busy} onClick={apply}>Önerileri uygula</button>
                <button type="button" className="button button-quiet" disabled={busy} onClick={() => setResult(null)}>Vazgeç</button>
              </div>
            </>
          ) : (
            <button type="button" className="button button-quiet" onClick={() => setResult(null)}>Kapat</button>
          )}
        </div>
      )}
    </section>
  );
}

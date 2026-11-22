import { useEffect, useState } from "react";
import { displayDate } from "./crmUtils.js";

const TYPE_LABELS = {
  basvuru_alindi: "Başvuru alındı bildirimi",
  mulakat_daveti: "Mülakat daveti",
  degerlendirme: "Test / ödev daveti",
  teklif: "İş teklifi",
  ret: "Olumsuz dönüş",
};

function changeSummary(item) {
  const parts = [];
  if (item.suggestion.status) parts.push(`durum → ${item.suggestion.status}`);
  if (item.suggestion.last_contact_date) parts.push(`son temas ${displayDate(item.suggestion.last_contact_date)}`);
  if (item.suggestion.task) parts.push(`görev: ${item.suggestion.task.description}`);
  return parts.join(" · ");
}

// Yönlendirilen e-postalardan çıkan bekleyen öneriler. Kendi verisini yükler; hata veya
// boş liste durumunda görünmez, böylece genel bakışın geri kalanını etkilemez.
export default function EmailSuggestionsCard({ api, token, reloadKey, onChanged }) {
  const [items, setItems] = useState([]);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    api.request("/email-insights/suggestions", { token })
      .then((result) => { if (active) setItems(Array.isArray(result) ? result : []); })
      .catch(() => { if (active) setItems([]); });
    return () => { active = false; };
  }, [api, token, reloadKey]);

  async function resolve(item, action) {
    setBusyId(item.id);
    setError("");
    try {
      await api.request(`/email-insights/suggestions/${item.id}/${action}`, { method: "POST", token });
      setItems((current) => current.filter((entry) => entry.id !== item.id));
      onChanged();
    } catch (resolveError) {
      if (resolveError.status !== 401) setError("Öneri güncellenemedi. Tekrar deneyebilirsin.");
    } finally {
      setBusyId(null);
    }
  }

  if (!items.length) return null;

  return (
    <section className="crm-overview-card email-suggestions" aria-labelledby="email-suggestions-title">
      <div className="crm-card-heading"><div><h3 id="email-suggestions-title">E-postadan gelen öneriler</h3><p>Yönlendirdiğin e-postalara göre; sen onaylamadan hiçbir şey değişmez</p></div></div>
      {error && <p className="form-error" role="alert">{error}</p>}
      <ul className="crm-task-summary">
        {items.map((item) => {
          const company = item.opportunity.company || "Şirket";
          return (
            <li key={item.id}>
              <span className={`crm-task-dot${item.email_type === "ret" ? " overdue" : ""}`} />
              <div>
                <strong>{company} · {TYPE_LABELS[item.email_type] || item.email_type}</strong>
                <small>{item.subject || "Konu yok"} · {displayDate(item.received_at)}</small>
                <small>Önerilen: {changeSummary(item)}</small>
              </div>
              <div className="email-suggestion-actions">
                <button className="text-button" type="button" disabled={busyId !== null} aria-label={`${company} önerisini uygula`} onClick={() => resolve(item, "apply")}>Uygula</button>
                <button className="text-button" type="button" disabled={busyId !== null} aria-label={`${company} önerisini reddet`} onClick={() => resolve(item, "dismiss")}>Reddet</button>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

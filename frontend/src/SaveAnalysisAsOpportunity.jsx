import { useState } from "react";

const today = () => {
  const date = new Date();
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
};

function httpUrlOrEmpty(value) {
  if (!value || value.length > 2048) return "";
  try {
    return ["http:", "https:"].includes(new URL(value).protocol) ? value : "";
  } catch {
    return "";
  }
}

// Ücret ilanda serbest metin olduğu için sayısal maaş alanına değil, notlara yazılır.
const NOTE_FIELDS = [
  ["salary", "İlandaki ücret"],
  ["employment_type", "Çalışma türü"],
  ["work_arrangement", "Çalışma düzeni"],
  ["experience", "Deneyim"],
  ["education", "Eğitim"],
];

function initialForm(result) {
  const metadata = result.metadata || {};
  const notes = NOTE_FIELDS
    .filter(([key]) => metadata[key]?.value)
    .map(([key, label]) => `${label}: ${metadata[key].value}`)
    .join("\n");
  return {
    company: (metadata.company?.value || "").slice(0, 200),
    position: (result.role || "").slice(0, 200),
    type: "İş",
    status: "Başvuruldu",
    location: (metadata.location?.value || "").slice(0, 200),
    job_link: httpUrlOrEmpty(metadata.application_url?.value),
    notes: notes.slice(0, 5000),
  };
}

function saveErrorMessage(error) {
  if (error.errorCode === "quota_exceeded") return "Hesabındaki başvuru sınırına ulaştın.";
  if (error.errorCode === "unknown_skill") return "Seçilen becerilerden biri artık katalogda yok. İlanı yeniden analiz edip tekrar dene.";
  if (error.status === 422) return "Bazı alanlar geçersiz. Bağlantının http(s) ile başladığını ve alanların çok uzun olmadığını kontrol et.";
  if (error.status === 429) return error.message;
  return "Başvuru kaydedilemedi. Lütfen tekrar dene.";
}

export default function SaveAnalysisAsOpportunity({ result, api, token, onNavigate }) {
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState(() => initialForm(result));
  const [selectedSkillIds, setSelectedSkillIds] = useState(
    () => new Set((result.skills || []).map((skill) => skill.skill_id)),
  );
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saved, setSaved] = useState(null);

  const change = (name, value) => setValues((current) => ({ ...current, [name]: value }));

  function toggleSkill(skillId) {
    setSelectedSkillIds((current) => {
      const next = new Set(current);
      if (next.has(skillId)) next.delete(skillId);
      else next.add(skillId);
      return next;
    });
  }

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setSaveError("");
    try {
      const skillIds = [...selectedSkillIds];
      const created = await api.request("/opportunities", {
        method: "POST",
        token,
        body: JSON.stringify({
          ...values,
          application_date: today(),
          last_contact_date: today(),
          salary: 0,
          next_action: "",
          skill_ids: skillIds,
        }),
      });
      setSaved({ ...created, skillCount: skillIds.length });
    } catch (error) {
      if (error.status !== 401) setSaveError(saveErrorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  if (saved) {
    return (
      <section className="save-analysis" aria-labelledby="save-analysis-title">
        <h4 id="save-analysis-title">Başvuru olarak kaydet</h4>
        <div className="notice" role="status">
          <span>
            <strong>{saved.company} · {saved.position}</strong> başvurularına eklendi
            {saved.skillCount > 0 ? `; ${saved.skillCount} beceri bağlandı.` : "."}
          </span>
        </div>
        <button type="button" className="button button-primary" onClick={() => onNavigate?.("opportunities")}>
          Başvurulara git
        </button>
      </section>
    );
  }

  if (!open) {
    return (
      <section className="save-analysis">
        <button type="button" className="button button-primary" onClick={() => setOpen(true)}>
          Bu ilanı başvuru olarak kaydet
        </button>
      </section>
    );
  }

  const skills = result.skills || [];
  return (
    <section className="save-analysis" aria-labelledby="save-analysis-title">
      <h4 id="save-analysis-title">Başvuru olarak kaydet</h4>
      <p className="analysis-explanation">
        Alanlar analizden dolduruldu; kaydetmeden önce kontrol et. Maaş, son tarih ve sonraki adımı sonra Başvurular ekranından düzenleyebilirsin.
      </p>
      <form className="crm-form" onSubmit={submit}>
        <div className="crm-field">
          <label htmlFor="save-company">Şirket</label>
          <input id="save-company" required maxLength={200} value={values.company} onChange={(e) => change("company", e.target.value)} />
        </div>
        <div className="crm-field">
          <label htmlFor="save-position">Pozisyon</label>
          <input id="save-position" required maxLength={200} value={values.position} onChange={(e) => change("position", e.target.value)} />
        </div>
        <div className="crm-field">
          <label htmlFor="save-type">Fırsat türü</label>
          <input id="save-type" required maxLength={50} list="save-opportunity-types" value={values.type} onChange={(e) => change("type", e.target.value)} />
        </div>
        <div className="crm-field">
          <label htmlFor="save-status">Durum</label>
          <input id="save-status" required maxLength={50} list="save-opportunity-statuses" value={values.status} onChange={(e) => change("status", e.target.value)} />
        </div>
        <div className="crm-field">
          <label htmlFor="save-location">Konum</label>
          <input id="save-location" maxLength={200} value={values.location} onChange={(e) => change("location", e.target.value)} />
        </div>
        <div className="crm-field">
          <label htmlFor="save-job-link">İlan bağlantısı</label>
          <input id="save-job-link" type="url" maxLength={2048} placeholder="https://…" value={values.job_link} onChange={(e) => change("job_link", e.target.value)} />
        </div>
        <div className="crm-field crm-field-wide">
          <label htmlFor="save-notes">Notlar</label>
          <textarea id="save-notes" maxLength={5000} rows={3} value={values.notes} onChange={(e) => change("notes", e.target.value)} />
        </div>
        <fieldset className="crm-field crm-field-wide">
          <legend>Başvuruya bağlanacak beceriler</legend>
          {skills.length === 0 ? (
            <p className="analysis-explanation">Analizde katalogda tanınan beceri bulunmadı.</p>
          ) : skills.map((skill) => (
            <label key={skill.skill_id} className="crm-checkbox">
              <input
                type="checkbox"
                checked={selectedSkillIds.has(skill.skill_id)}
                onChange={() => toggleSkill(skill.skill_id)}
              />
              {skill.name}
            </label>
          ))}
        </fieldset>
        <datalist id="save-opportunity-types">
          <option value="İş" /><option value="Staj" /><option value="Freelance" />
        </datalist>
        <datalist id="save-opportunity-statuses">
          <option value="Başvuruldu" /><option value="Ön görüşme" /><option value="Teknik mülakat" />
          <option value="Son mülakat" /><option value="Teklif" /><option value="Reddedildi" />
        </datalist>
        {saveError && <p className="form-error crm-field-wide" role="alert">{saveError}</p>}
        <div className="crm-form-actions crm-field-wide">
          <button className="button button-primary" disabled={busy}>{busy ? "Kaydediliyor…" : "Başvuru olarak kaydet"}</button>
        </div>
      </form>
    </section>
  );
}

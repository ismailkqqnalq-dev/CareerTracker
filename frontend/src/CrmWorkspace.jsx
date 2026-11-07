import { useCallback, useEffect, useMemo, useState } from "react";

const PAGE_SIZE = 50;
const today = () => {
  const date = new Date();
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
};

const RESOURCES = {
  opportunities: {
    path: "/opportunities",
    title: "Başvurular",
    singular: "başvuru",
    description: "İş, staj ve freelance fırsatlarını ve başvuru süreçlerini takip et.",
    fields: [
      { name: "company", label: "Şirket", kind: "text", required: true, maxLength: 200 },
      { name: "position", label: "Pozisyon", kind: "text", required: true, maxLength: 200 },
      { name: "type", label: "Fırsat türü", kind: "text", required: true, maxLength: 50, placeholder: "İş, staj, freelance…", list: "opportunity-types" },
      { name: "application_date", label: "Başvuru tarihi", kind: "date", required: true },
      { name: "status", label: "Durum", kind: "text", required: true, maxLength: 50, list: "opportunity-statuses" },
      { name: "salary", label: "Maaş / ücret", kind: "number", required: true, min: 0 },
      { name: "location", label: "Konum", kind: "text", required: true, maxLength: 200 },
      { name: "job_link", label: "İlan bağlantısı", kind: "url", required: true, maxLength: 2048, placeholder: "https://…" },
      { name: "last_contact_date", label: "Son iletişim tarihi", kind: "date", required: true },
      { name: "next_action", label: "Sonraki adım", kind: "text", required: true, maxLength: 500 },
      { name: "notes", label: "Notlar", kind: "textarea", required: true, maxLength: 5000, wide: true },
    ],
  },
  contacts: {
    path: "/contacts",
    title: "Kişiler",
    singular: "kişi",
    description: "Başvuru sürecinde tanıştığın kişileri ve iletişim bilgilerini düzenle.",
    fields: [
      { name: "name", label: "Ad soyad", kind: "text", required: true, maxLength: 200 },
      { name: "role", label: "Görev / rol", kind: "text", required: true, maxLength: 200 },
      { name: "email", label: "E-posta", kind: "email", required: true, maxLength: 320 },
      { name: "linkedin", label: "LinkedIn bağlantısı", kind: "url", required: true, maxLength: 2048, placeholder: "https://…" },
      { name: "opportunity_id", label: "Bağlı başvuru", kind: "relation", relation: "opportunities", required: true, wide: true },
    ],
  },
  tasks: {
    path: "/tasks",
    title: "Görevler",
    singular: "görev",
    description: "Başvuruların için takip ve hatırlatma görevlerini planla.",
    fields: [
      { name: "description", label: "Görev", kind: "textarea", required: true, maxLength: 2000, wide: true },
      { name: "opportunity_id", label: "Bağlı başvuru", kind: "relation", relation: "opportunities", required: true, wide: true },
      { name: "due_date", label: "Son tarih", kind: "date", required: true },
      { name: "is_completed", label: "Tamamlandı", kind: "checkbox", wide: true },
    ],
  },
  activities: {
    path: "/activities",
    title: "Aktiviteler",
    singular: "aktivite",
    description: "Görüşme, e-posta ve diğer başvuru temaslarını zaman çizelgesinde tut.",
    fields: [
      { name: "activity_type", label: "Aktivite türü", kind: "text", required: true, maxLength: 100, placeholder: "Görüşme, e-posta…" },
      { name: "dates", label: "Tarih", kind: "date", required: true },
      { name: "opportunity_id", label: "Bağlı başvuru", kind: "relation", relation: "opportunities", required: true },
      { name: "contact_id", label: "İlgili kişi (isteğe bağlı)", kind: "relation", relation: "contacts", wide: true },
      { name: "notes", label: "Notlar", kind: "textarea", required: true, maxLength: 5000, wide: true },
    ],
  },
};

const VIEW_TITLES = {
  overview: "Genel bakış",
  opportunities: "Başvurular",
  contacts: "Kişiler",
  tasks: "Görevler",
  activities: "Aktiviteler",
};

function displayDate(value) {
  if (!value) return "Tarih yok";
  const parsed = new Date(`${String(value).slice(0, 10)}T12:00:00`);
  return Number.isNaN(parsed.valueOf()) ? String(value) : new Intl.DateTimeFormat("tr-TR", { dateStyle: "medium" }).format(parsed);
}

function safeHttpUrl(value) {
  if (!value) return null;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function relationName(resource, id, related) {
  if (!id) return "Bağlı kayıt yok";
  if (resource === "opportunities") {
    const record = related.opportunities.find((item) => item.id === id);
    return record ? `${record.company || "Şirket"} · ${record.position || "Pozisyon"}` : `Başvuru #${id}`;
  }
  const record = related.contacts.find((item) => item.id === id);
  return record?.name || `Kişi #${id}`;
}

function initialValues(config, record) {
  return Object.fromEntries(config.fields.map((field) => {
    let value = record?.[field.name];
    if (field.kind === "date") value = value ? String(value).slice(0, 10) : today();
    else if (field.kind === "checkbox") value = Boolean(value);
    else if (field.kind === "number") value = value ?? (record ? "" : 0);
    else value = value == null ? "" : String(value);
    return [field.name, value];
  }));
}

function toPayload(config, values) {
  return Object.fromEntries(config.fields.map((field) => {
    let value = values[field.name];
    if (field.kind === "relation") value = value === "" ? null : Number(value);
    if (field.kind === "number") value = value === "" ? null : Number(value);
    if (field.kind === "checkbox") value = Boolean(value);
    return [field.name, value];
  }));
}

function RelationControl({ field, value, onChange, related }) {
  const [query, setQuery] = useState("");
  const options = related[field.relation] || [];
  const normalizedQuery = query.trim().toLocaleLowerCase("tr-TR");
  const matching = options.filter((item) => {
    const label = field.relation === "opportunities"
      ? `${item.company || ""} ${item.position || ""} ${item.id}`
      : `${item.name || ""} ${item.role || ""} ${item.id}`;
    return !normalizedQuery || label.toLocaleLowerCase("tr-TR").includes(normalizedQuery);
  });
  const selectedOption = options.find((item) => String(item.id) === String(value));
  const filtered = matching.slice(0, 60);
  if (selectedOption && !filtered.some((item) => item.id === selectedOption.id)) filtered.unshift(selectedOption);

  return (
    <div className="crm-relation-control">
      <input
        aria-label={`${field.label} içinde ara`}
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Şirket, pozisyon veya kişi ara…"
      />
      <select
        aria-label={field.label}
        required={field.required}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">{field.required ? "Kayıt seç" : "Kişi seçme (isteğe bağlı)"}</option>
        {filtered.map((item) => (
          <option key={item.id} value={item.id}>
            {field.relation === "opportunities"
              ? `#${item.id} · ${item.company || "Şirket"} — ${item.position || "Pozisyon"}`
              : `#${item.id} · ${item.name || "İsimsiz kişi"}${item.role ? ` — ${item.role}` : ""}`}
          </option>
        ))}
      </select>
      {options.length === 0 && <small>{field.relation === "opportunities" ? "Önce bir başvuru kaydı eklemelisin." : "Henüz kişi kaydı yok; bu alanı boş bırakabilirsin."}</small>}
      {normalizedQuery && filtered.length === 0 && <small>Bu aramayla eşleşen kayıt yok.</small>}
    </div>
  );
}

function RecordEditor({ config, record, related, onCancel, onSave, busy }) {
  const [values, setValues] = useState(() => initialValues(config, record));
  const [saveError, setSaveError] = useState("");

  function change(name, value) {
    setValues((current) => ({ ...current, [name]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setSaveError("");
    try {
      await onSave(toPayload(config, values));
    } catch {
      setSaveError("Kayıt kaydedilemedi. Alanları ve bağlı başvuruyu kontrol edip tekrar dene.");
    }
  }

  return (
    <section className="crm-editor" aria-labelledby="crm-editor-title">
      <div className="crm-editor-heading">
        <div>
          <p className="eyebrow">{record ? "KAYDI DÜZENLE" : "YENİ KAYIT"}</p>
          <h3 id="crm-editor-title">{record ? `${config.singular} bilgilerini güncelle` : `Yeni ${config.singular} ekle`}</h3>
        </div>
        <button type="button" className="button button-quiet" onClick={onCancel}>Kapat</button>
      </div>
      <form className="crm-form" onSubmit={submit}>
        {config.fields.map((field) => (
          <div key={field.name} className={`crm-field${field.wide ? " crm-field-wide" : ""}`}>
            {field.kind !== "checkbox" && <label htmlFor={`crm-${field.name}`}>{field.label}</label>}
            {field.kind === "relation" ? (
              <RelationControl
                field={field}
                value={values[field.name]}
                onChange={(value) => change(field.name, value)}
                related={related}
              />
            ) : field.kind === "textarea" ? (
              <textarea
                id={`crm-${field.name}`}
                required={field.required}
                maxLength={field.maxLength ?? 2000}
                rows={3}
                value={values[field.name]}
                onChange={(event) => change(field.name, event.target.value)}
              />
            ) : field.kind === "checkbox" ? (
              <label className="crm-checkbox" htmlFor={`crm-${field.name}`}>
                <input
                  id={`crm-${field.name}`}
                  type="checkbox"
                  checked={values[field.name]}
                  onChange={(event) => change(field.name, event.target.checked)}
                />
                {field.label}
              </label>
            ) : (
              <input
                id={`crm-${field.name}`}
                type={field.kind}
                required={field.required}
                min={field.min}
                maxLength={field.maxLength ?? 500}
                placeholder={field.placeholder}
                list={field.list}
                value={values[field.name]}
                onChange={(event) => change(field.name, event.target.value)}
              />
            )}
          </div>
        ))}
        <datalist id="opportunity-types">
          <option value="İş" /><option value="Staj" /><option value="Freelance" />
        </datalist>
        <datalist id="opportunity-statuses">
          <option value="Başvuruldu" /><option value="Ön görüşme" /><option value="Teknik mülakat" />
          <option value="Son mülakat" /><option value="Teklif" /><option value="Reddedildi" />
        </datalist>
        {saveError && <p className="form-error crm-field-wide" role="alert">{saveError}</p>}
        <div className="crm-form-actions crm-field-wide">
          <button type="button" className="button button-quiet" onClick={onCancel}>Vazgeç</button>
          <button className="button button-primary" disabled={busy}>{busy ? "Kaydediliyor…" : "Kaydet"}</button>
        </div>
      </form>
    </section>
  );
}

function RecordCard({ view, record, related, onEdit, onDelete, onToggleTask }) {
  const opportunity = view === "opportunities";
  const contact = view === "contacts";
  const task = view === "tasks";
  const safeLink = opportunity ? safeHttpUrl(record.job_link) : contact ? safeHttpUrl(record.linkedin) : null;
  const title = opportunity
    ? (record.position || "Pozisyon belirtilmedi")
    : contact ? (record.name || "İsimsiz kişi")
      : task ? (record.description || "Görev")
        : (record.activity_type || "Aktivite");

  return (
    <article className={`crm-record-card${task && record.is_completed ? " is-complete" : ""}`}>
      <div className="crm-record-main">
        <div className="crm-record-title-row">
          {task && (
            <button
              type="button"
              className={`crm-task-check${record.is_completed ? " checked" : ""}`}
              aria-label={record.is_completed ? "Görevi tamamlanmadı işaretle" : "Görevi tamamlandı işaretle"}
              aria-pressed={Boolean(record.is_completed)}
              onClick={() => onToggleTask(record)}
            >{record.is_completed ? "✓" : ""}</button>
          )}
          <div className="crm-record-title-copy">
            {opportunity && <span className="crm-record-company">{record.company || "Şirket belirtilmedi"}</span>}
            <h3>{title}</h3>
            {contact && <p>{record.role || "Rol belirtilmedi"}</p>}
          </div>
          {opportunity && <span className="crm-status-pill">{record.status || "Durum yok"}</span>}
          {task && <span className={`crm-status-pill ${record.is_completed ? "success" : "warning"}`}>{record.is_completed ? "Tamamlandı" : "Açık"}</span>}
        </div>
        <div className="crm-record-meta">
          {opportunity && <>
            <span>{record.type || "Tür belirtilmedi"}</span>
            <span>{record.location || "Konum yok"}</span>
            <span>{displayDate(record.application_date)}</span>
            {record.salary != null && <span>{new Intl.NumberFormat("tr-TR").format(record.salary)} ücret</span>}
            {record.next_action && <span className="crm-meta-emphasis">Sonraki adım: {record.next_action}</span>}
          </>}
          {contact && <>
            {record.email && <a href={`mailto:${record.email}`}>{record.email}</a>}
            <span>{relationName("opportunities", record.opportunity_id, related)}</span>
          </>}
          {task && <>
            <span>{relationName("opportunities", record.opportunity_id, related)}</span>
            <span>Son tarih: {displayDate(record.due_date)}</span>
          </>}
          {!opportunity && !contact && !task && <>
            <span>{relationName("opportunities", record.opportunity_id, related)}</span>
            {record.contact_id && <span>{relationName("contacts", record.contact_id, related)}</span>}
            <span>{displayDate(record.dates)}</span>
          </>}
        </div>
        {record.notes && <p className="crm-record-notes">{record.notes}</p>}
        {safeLink && <a className="crm-record-link" href={safeLink} target="_blank" rel="noreferrer">{opportunity ? "İlanı aç" : "LinkedIn profilini aç"} ↗</a>}
      </div>
      <div className="crm-record-actions">
        <button type="button" className="button button-quiet" onClick={() => onEdit(record)}>Düzenle</button>
        <button type="button" className="button button-danger-quiet" onClick={() => onDelete(record)}>Sil</button>
      </div>
    </article>
  );
}

function StatCard({ label, value, hint, accent = "" }) {
  return (
    <article className={`crm-stat-card ${accent}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{hint}</small>
    </article>
  );
}

function Overview({ api, token, onNavigate }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    async function load() {
      try {
        const [stats, opportunities, contacts, tasks, activities] = await Promise.all([
          api.request("/dashboard", { token }),
          api.requestPage("/opportunities", { token, limit: 5, offset: 0 }),
          api.requestPage("/contacts", { token, limit: 1, offset: 0 }),
          api.requestPage("/tasks", { token, limit: 5, offset: 0 }),
          api.requestPage("/activities", { token, limit: 1, offset: 0 }),
        ]);
        const [recentOpportunities, recentTasks] = await Promise.all([
          opportunities.totalCount > 5
            ? api.requestPage("/opportunities", { token, limit: 5, offset: opportunities.totalCount - 5 })
            : Promise.resolve(opportunities),
          tasks.totalCount > 5
            ? api.requestPage("/tasks", { token, limit: 5, offset: tasks.totalCount - 5 })
            : Promise.resolve(tasks),
        ]);
        if (active) setData({ stats, opportunities: recentOpportunities.items, contacts, tasks: recentTasks.items, activities });
      } catch {
        if (active) setError("Genel bakış yüklenemedi. Bağlantını kontrol edip tekrar deneyebilirsin.");
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => { active = false; };
  }, [api, token, reloadKey]);

  const statusEntries = Object.entries(data?.stats?.by_status || {}).sort((left, right) => right[1] - left[1]);
  const maxStatus = Math.max(1, ...statusEntries.map(([, count]) => count));

  return (
    <section className="crm-overview" aria-labelledby="overview-title">
      <div className="crm-overview-intro">
        <div>
          <p className="eyebrow">KİŞİSEL ÇALIŞMA ALANIN</p>
          <h2 id="overview-title">Kariyer sürecin, tek yerde.</h2>
          <p className="muted">Başvurularını, görüşmelerini ve takip adımlarını düzenli tut.</p>
        </div>
        <button className="button button-primary" type="button" onClick={() => onNavigate("opportunities")}>+ Yeni başvuru</button>
      </div>

      {error && <div className="alert" role="alert"><span>{error}</span><button className="button button-quiet" type="button" onClick={() => setReloadKey((value) => value + 1)}>Yeniden dene</button></div>}
      {loading ? <div className="crm-loading" role="status">Özet yükleniyor…</div> : data && <>
        <div className="crm-stat-grid">
          <StatCard label="Toplam başvuru" value={data.stats.total_opportunities ?? 0} hint="Kayıtlı fırsatların" accent="purple" />
          <StatCard label="Görüşme aşaması" value={data.stats.interview_count ?? 0} hint="Ön, teknik ve son görüşmeler" />
          <StatCard label="Teklif" value={data.stats.offer_count ?? 0} hint="Teklif aldığın fırsatlar" accent="green" />
          <StatCard label="Kişi" value={data.contacts.totalCount} hint="İletişim kayıtların" />
        </div>

        <div className="crm-overview-grid">
          <section className="crm-overview-card" aria-labelledby="status-breakdown-title">
            <div className="crm-card-heading"><div><h3 id="status-breakdown-title">Başvuru durumları</h3><p>Fırsatların hangi aşamada?</p></div><button className="text-button" type="button" onClick={() => onNavigate("opportunities")}>Tüm başvurular</button></div>
            {statusEntries.length ? <ul className="crm-status-breakdown">{statusEntries.map(([status, count]) => (
              <li key={status || "unknown"}>
                <div><span>{status || "Durum belirtilmedi"}</span><strong>{count}</strong></div>
                <span className="crm-status-track" aria-hidden="true"><span style={{ width: `${(count / maxStatus) * 100}%` }} /></span>
              </li>
            ))}</ul> : <p className="crm-empty-inline">Henüz başvuru kaydı yok.</p>}
            <p className="crm-disclaimer">Teklif oranı veya işe girme olasılığı olarak yorumlanmamalıdır.</p>
          </section>

          <section className="crm-overview-card" aria-labelledby="recent-opportunities-title">
            <div className="crm-card-heading"><div><h3 id="recent-opportunities-title">Son başvurular</h3><p>En son eklediğin fırsatlar</p></div><button className="text-button" type="button" onClick={() => onNavigate("opportunities")}>Hepsini gör</button></div>
            {data.opportunities.length ? <ul className="crm-recent-list">{[...data.opportunities].reverse().map((item) => (
              <li key={item.id}><span className="crm-recent-mark">{(item.company || "Ş").slice(0, 1).toLocaleUpperCase("tr-TR")}</span><div><strong>{item.company || "Şirket"}</strong><small>{item.position || "Pozisyon belirtilmedi"}</small></div><span className="crm-status-pill">{item.status || "Durum yok"}</span></li>
            ))}</ul> : <p className="crm-empty-inline">İlk başvurunu ekleyerek başlayabilirsin.</p>}
          </section>

          <section className="crm-overview-card" aria-labelledby="tasks-summary-title">
            <div className="crm-card-heading"><div><h3 id="tasks-summary-title">Takip görevleri</h3><p>{data.tasks.totalCount} görev kayıtlı</p></div><button className="text-button" type="button" onClick={() => onNavigate("tasks")}>Görevleri aç</button></div>
            {data.tasks.length ? <ul className="crm-task-summary">{[...data.tasks].reverse().map((task) => (
              <li key={task.id}><span className={`crm-task-dot${task.is_completed ? " done" : ""}`} /><div><strong>{task.description}</strong><small>{displayDate(task.due_date)}</small></div><span>{task.is_completed ? "Tamamlandı" : "Açık"}</span></li>
            ))}</ul> : <p className="crm-empty-inline">Takip etmen gereken bir görev yok.</p>}
          </section>

          <section className="crm-overview-card crm-shortcuts" aria-labelledby="shortcuts-title">
            <div className="crm-card-heading"><div><h3 id="shortcuts-title">Hızlı erişim</h3><p>Çalışma alanının diğer bölümleri</p></div></div>
            <div className="crm-shortcut-grid">
              <button type="button" onClick={() => onNavigate("contacts")}><span>↗</span><strong>Kişiler</strong><small>{data.contacts.totalCount} kayıt</small></button>
              <button type="button" onClick={() => onNavigate("activities")}><span>◷</span><strong>Aktiviteler</strong><small>{data.activities.totalCount} kayıt</small></button>
              <button type="button" onClick={() => onNavigate("profile")}><span>◎</span><strong>Beceri profili</strong><small>Profilini ve eşleşmeni gör</small></button>
              <button type="button" onClick={() => onNavigate("suggestions")}><span>⌕</span><strong>İlan & beceri merkezi</strong><small>OCR ve ilan analizi</small></button>
            </div>
          </section>
        </div>
      </>}
    </section>
  );
}

export default function CrmWorkspace({ api, token, view, onNavigate }) {
  if (view === "overview") return <Overview api={api} token={token} onNavigate={onNavigate} />;
  return <ResourceWorkspace api={api} token={token} view={view} />;
}

function ResourceWorkspace({ api, token, view }) {
  const config = RESOURCES[view];
  const [offsets, setOffsets] = useState({});
  const offset = offsets[view] || 0;
  const [records, setRecords] = useState([]);
  const [total, setTotal] = useState(0);
  const [related, setRelated] = useState({ opportunities: [], contacts: [] });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");
  const [editor, setEditor] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const page = await api.requestPage(config.path, { token, limit: PAGE_SIZE, offset });
      setRecords(page.items);
      setTotal(page.totalCount);
      if (view === "opportunities") {
        setRelated({ opportunities: [], contacts: [] });
      } else {
        const [opportunities, contacts] = await Promise.all([
          api.requestAll("/opportunities", { token, pageSize: 200 }),
          view === "activities" ? api.requestAll("/contacts", { token, pageSize: 200 }) : Promise.resolve([]),
        ]);
        setRelated({ opportunities, contacts });
      }
    } catch {
      setError(`${config.title} yüklenemedi. Bağlantını kontrol edip yeniden dene.`);
    } finally {
      setLoading(false);
    }
  }, [api, config.path, config.title, offset, token, view]);

  useEffect(() => { load(); }, [load, reloadKey]);

  const filteredRecords = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("tr-TR");
    const rows = needle ? records.filter((record) => Object.values(record).some((value) => String(value ?? "").toLocaleLowerCase("tr-TR").includes(needle))) : records;
    return [...rows].sort((left, right) => right.id - left.id);
  }, [query, records]);

  async function save(payload) {
    setBusy(true);
    try {
      const editing = editor?.mode === "edit" ? editor.record : null;
      await api.request(editing ? `${config.path}/${editing.id}` : config.path, {
        method: editing ? "PATCH" : "POST",
        token,
        body: JSON.stringify(payload),
      });
      setEditor(null);
      setNotice(editing ? `${config.singular} güncellendi.` : `Yeni ${config.singular} eklendi.`);
      setReloadKey((value) => value + 1);
    } catch (saveError) {
      if (saveError.status === 409 && saveError.errorCode === "quota_exceeded") {
        throw new Error("Başvuru kotasına ulaşıldı.");
      }
      throw saveError;
    } finally {
      setBusy(false);
    }
  }

  async function remove(record) {
    const cascadeNote = view === "opportunities"
      ? " Bu başvuruya bağlı kişiler, görevler ve aktiviteler de silinir."
      : view === "contacts" ? " Kişiye bağlı aktiviteler korunur." : "";
    if (!window.confirm(`“${record.company || record.name || record.description || record.activity_type || config.singular}” silinsin mi?${cascadeNote}`)) return;
    setError("");
    setNotice("");
    try {
      await api.request(`${config.path}/${record.id}`, { method: "DELETE", token });
      setNotice(`${config.singular} silindi.`);
      if (records.length === 1 && offset > 0) {
        setOffsets((current) => ({ ...current, [view]: Math.max(0, offset - PAGE_SIZE) }));
      } else {
        setReloadKey((value) => value + 1);
      }
    } catch {
      setError(`${config.singular} silinemedi. Kayıt güncel olmayabilir; listeyi yenileyip tekrar dene.`);
    }
  }

  async function toggleTask(record) {
    try {
      await api.request(`/tasks/${record.id}`, {
        method: "PATCH",
        token,
        body: JSON.stringify({ is_completed: !record.is_completed }),
      });
      setNotice(record.is_completed ? "Görev yeniden açıldı." : "Görev tamamlandı olarak işaretlendi.");
      setReloadKey((value) => value + 1);
    } catch {
      setError("Görev durumu güncellenemedi. Tekrar dene.");
    }
  }

  const pageNumber = Math.floor(offset / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <section className="crm-resource" aria-labelledby="crm-resource-title">
      <div className="crm-resource-heading">
        <div><p className="eyebrow">KİŞİSEL CRM</p><h2 id="crm-resource-title">{config.title}</h2><p className="muted">{config.description}</p></div>
        <button className="button button-primary" type="button" onClick={() => setEditor({ mode: "create" })}>+ Yeni {config.singular}</button>
      </div>

      {notice && <div className="notice" role="status"><span>{notice}</span><button className="text-button" type="button" onClick={() => setNotice("")}>Kapat</button></div>}
      {error && <div className="alert" role="alert"><span>{error}</span><button className="button button-quiet" type="button" onClick={() => setReloadKey((value) => value + 1)}>Yeniden dene</button></div>}

      {editor && (
        <RecordEditor
          key={`${view}-${editor.mode}-${editor.record?.id || "new"}`}
          config={config}
          record={editor.mode === "edit" ? editor.record : null}
          related={related}
          busy={busy}
          onCancel={() => setEditor(null)}
          onSave={save}
        />
      )}

      <div className="crm-list-toolbar">
        <label htmlFor="crm-search">Bu sayfada ara</label>
        <input id="crm-search" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={`${config.title} içinde ara…`} />
        <button className="button button-quiet" type="button" onClick={() => setReloadKey((value) => value + 1)} disabled={loading}>Yenile</button>
      </div>

      {loading ? <div className="crm-loading" role="status">{config.title} yükleniyor…</div> : filteredRecords.length ? (
        <>
          <div className="crm-record-list" aria-label={config.title}>
            {filteredRecords.map((record) => (
              <RecordCard
                key={record.id}
                view={view}
                record={record}
                related={related}
                onEdit={(item) => setEditor({ mode: "edit", record: item })}
                onDelete={remove}
                onToggleTask={toggleTask}
              />
            ))}
          </div>
          {query && filteredRecords.length < records.length && <p className="crm-filter-note">Arama yalnızca bu sayfadaki {records.length} kaydı süzer.</p>}
        </>
      ) : (
        <section className="crm-empty-state">
          <span>{query ? "⌕" : "＋"}</span>
          <h3>{query ? "Eşleşen kayıt yok" : `Henüz ${config.singular} yok`}</h3>
          <p>{query ? "Arama ifadesini kısaltabilir veya silebilirsin." : `${config.description} İlk kaydını ekleyerek başlayabilirsin.`}</p>
          {!query && <button className="button button-primary" type="button" onClick={() => setEditor({ mode: "create" })}>İlk {config.singular} kaydını ekle</button>}
          {query && <button className="button button-quiet" type="button" onClick={() => setQuery("")}>Aramayı temizle</button>}
        </section>
      )}

      <div className="crm-pagination">
        <span>{total} kayıt · sayfa {pageNumber}/{pageCount}</span>
        <div>
          <button className="button button-quiet" type="button" disabled={loading || offset === 0} onClick={() => setOffsets((current) => ({ ...current, [view]: Math.max(0, offset - PAGE_SIZE) }))}>Önceki</button>
          <button className="button button-quiet" type="button" disabled={loading || offset + PAGE_SIZE >= total} onClick={() => setOffsets((current) => ({ ...current, [view]: offset + PAGE_SIZE }))}>Sonraki</button>
        </div>
      </div>
    </section>
  );
}

export { VIEW_TITLES };

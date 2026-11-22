import { useEffect, useMemo, useState } from "react";
import { OPPORTUNITY_STATUSES, displayDate, safeHttpUrl, today } from "./crmUtils.js";
import EmailUpdatePanel from "./EmailUpdatePanel.jsx";

function timelineOf(detail) {
  const contactNames = Object.fromEntries(detail.contacts.map((contact) => [contact.id, contact.name]));
  const entries = [
    ...detail.tasks.map((task) => ({ kind: "task", key: `task-${task.id}`, date: task.due_date, task })),
    ...detail.activities.map((activity) => ({
      kind: "activity",
      key: `activity-${activity.id}`,
      date: activity.dates,
      activity,
      contactName: contactNames[activity.contact_id] || null,
    })),
  ];
  // En yeni/en ileri tarih üstte; tarihsiz kayıtlar sonda.
  return entries.sort((left, right) => String(right.date || "").localeCompare(String(left.date || "")));
}

function QuickTaskForm({ onAdd, busy }) {
  const [description, setDescription] = useState("");
  const [dueDate, setDueDate] = useState(today());

  async function submit(event) {
    event.preventDefault();
    if (await onAdd({ description: description.trim(), due_date: dueDate })) setDescription("");
  }

  return (
    <form className="detail-quick-form" onSubmit={submit} aria-label="Görev ekle">
      <label htmlFor="detail-task-description">Yeni görev</label>
      <input id="detail-task-description" required maxLength={2000} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Örnek: Teşekkür e-postası gönder" />
      <label htmlFor="detail-task-due">Son tarih</label>
      <input id="detail-task-due" type="date" required value={dueDate} onChange={(event) => setDueDate(event.target.value)} />
      <button className="button button-primary" disabled={busy || !description.trim()}>Görevi ekle</button>
    </form>
  );
}

function QuickActivityForm({ contacts, onAdd, busy }) {
  const [activityType, setActivityType] = useState("Not");
  const [date, setDate] = useState(today());
  const [notes, setNotes] = useState("");
  const [contactId, setContactId] = useState("");

  async function submit(event) {
    event.preventDefault();
    const added = await onAdd({
      activity_type: activityType.trim(),
      dates: date,
      notes: notes.trim(),
      contact_id: contactId ? Number(contactId) : null,
    });
    if (added) setNotes("");
  }

  return (
    <form className="detail-quick-form" onSubmit={submit} aria-label="Not veya aktivite ekle">
      <label htmlFor="detail-activity-type">Tür</label>
      <input id="detail-activity-type" required maxLength={100} list="detail-activity-types" value={activityType} onChange={(event) => setActivityType(event.target.value)} />
      <datalist id="detail-activity-types">
        {["Not", "Görüşme", "E-posta", "Telefon", "Mülakat"].map((type) => <option key={type} value={type} />)}
      </datalist>
      <label htmlFor="detail-activity-date">Tarih</label>
      <input id="detail-activity-date" type="date" required value={date} onChange={(event) => setDate(event.target.value)} />
      {contacts.length > 0 && (
        <>
          <label htmlFor="detail-activity-contact">İlgili kişi</label>
          <select id="detail-activity-contact" value={contactId} onChange={(event) => setContactId(event.target.value)}>
            <option value="">Kişi seçilmedi</option>
            {contacts.map((contact) => <option key={contact.id} value={contact.id}>{contact.name}</option>)}
          </select>
        </>
      )}
      <label htmlFor="detail-activity-notes">Not</label>
      <textarea id="detail-activity-notes" required maxLength={5000} rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} />
      <button className="button button-primary" disabled={busy || !notes.trim() || !activityType.trim()}>Notu ekle</button>
    </form>
  );
}

export default function OpportunityDetail({ api, token, opportunityId, onBack }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    api.request(`/opportunities/${opportunityId}/detail`, { token })
      .then((result) => { if (active) { setDetail(result); setError(""); } })
      .catch((loadError) => {
        if (!active || loadError.status === 401) return;
        setError(loadError.status === 404
          ? "Bu başvuru bulunamadı; silinmiş olabilir."
          : "Başvuru ayrıntıları yüklenemedi. Bağlantını kontrol edip tekrar dene.");
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [api, token, opportunityId, reloadKey]);

  const timeline = useMemo(() => (detail ? timelineOf(detail) : []), [detail]);

  async function change(path, method, body, successMessage, failureMessage) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.request(path, { method, token, body: JSON.stringify(body) });
      setNotice(successMessage);
      setReloadKey((value) => value + 1);
      return true;
    } catch (changeError) {
      if (changeError.status !== 401) setError(failureMessage);
      return false;
    } finally {
      setBusy(false);
    }
  }

  const header = (
    <button type="button" className="button button-quiet detail-back" onClick={onBack}>← Başvurulara dön</button>
  );

  if (loading && !detail) {
    return <section className="crm-resource">{header}<div className="crm-loading" role="status">Başvuru yükleniyor…</div></section>;
  }
  if (!detail) {
    return (
      <section className="crm-resource">
        {header}
        <div className="alert" role="alert"><span>{error}</span><button className="button button-quiet" type="button" onClick={() => setReloadKey((value) => value + 1)}>Yeniden dene</button></div>
      </section>
    );
  }

  const { opportunity, contacts, skills } = detail;
  const jobLink = safeHttpUrl(opportunity.job_link);
  const id = opportunity.id;

  return (
    <section className="crm-resource opportunity-detail" aria-labelledby="opportunity-detail-title">
      {header}
      {notice && <div className="notice" role="status"><span>{notice}</span><button className="text-button" type="button" onClick={() => setNotice("")}>Kapat</button></div>}
      {error && <div className="alert" role="alert"><span>{error}</span></div>}

      <div className="detail-header">
        <div>
          <p className="eyebrow">{opportunity.company || "Şirket belirtilmedi"}</p>
          <h2 id="opportunity-detail-title">{opportunity.position || "Pozisyon belirtilmedi"}</h2>
          <p className="muted">
            {[opportunity.type, opportunity.location, `Başvuru: ${displayDate(opportunity.application_date)}`].filter(Boolean).join(" · ")}
          </p>
        </div>
        <select
          className="crm-status-pill crm-status-select"
          aria-label="Başvuru durumu"
          value={opportunity.status || ""}
          disabled={busy}
          onChange={(event) => change(`/opportunities/${id}`, "PATCH", { status: event.target.value }, `Durum “${event.target.value}” olarak güncellendi.`, "Durum güncellenemedi. Tekrar dene.")}
        >
          {!OPPORTUNITY_STATUSES.includes(opportunity.status) && (
            <option value={opportunity.status || ""} disabled>{opportunity.status ? `${opportunity.status} (eski değer)` : "Durum yok"}</option>
          )}
          {OPPORTUNITY_STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
        </select>
      </div>

      <dl className="detail-facts">
        <div><dt>Son temas</dt><dd>{displayDate(opportunity.last_contact_date)}</dd></div>
        <div><dt>Sıradaki adım</dt><dd>{opportunity.next_action || "Belirtilmedi"}</dd></div>
        {opportunity.salary ? <div><dt>Ücret</dt><dd>{new Intl.NumberFormat("tr-TR").format(opportunity.salary)}</dd></div> : null}
      </dl>
      <div className="detail-actions">
        <button
          type="button"
          className="button button-quiet"
          disabled={busy || opportunity.last_contact_date === today()}
          onClick={() => change(`/opportunities/${id}`, "PATCH", { last_contact_date: today() }, "Son temas tarihi bugün olarak kaydedildi.", "Son temas tarihi kaydedilemedi. Tekrar dene.")}
        >Bugün iletişime geçtim</button>
        {jobLink && <a className="crm-record-link" href={jobLink} target="_blank" rel="noreferrer">İlanı aç ↗</a>}
      </div>
      {opportunity.notes && <p className="crm-record-notes">{opportunity.notes}</p>}

      {skills.length > 0 && (
        <section aria-labelledby="detail-skills-title">
          <h3 id="detail-skills-title">İlandaki beceriler</h3>
          <ul className="detail-chips">{skills.map((skill) => <li key={skill.id}>{skill.name}</li>)}</ul>
        </section>
      )}

      <section aria-labelledby="detail-contacts-title">
        <h3 id="detail-contacts-title">Kişiler</h3>
        {contacts.length ? (
          <ul className="detail-list">
            {contacts.map((contact) => {
              const linkedin = safeHttpUrl(contact.linkedin);
              return (
                <li key={contact.id}>
                  <strong>{contact.name || "İsimsiz kişi"}</strong>
                  <span>{contact.role || "Rol belirtilmedi"}</span>
                  {contact.email && <a href={`mailto:${contact.email}`}>{contact.email}</a>}
                  {linkedin && <a href={linkedin} target="_blank" rel="noreferrer">LinkedIn ↗</a>}
                </li>
              );
            })}
          </ul>
        ) : <p className="muted">Bu başvuruya bağlı kişi yok. Kişiler ekranından ekleyebilirsin.</p>}
      </section>

      <section aria-labelledby="detail-timeline-title">
        <h3 id="detail-timeline-title">Zaman çizelgesi</h3>
        {timeline.length ? (
          <ol className="detail-timeline" aria-label="Zaman çizelgesi">
            {timeline.map((entry) => entry.kind === "task" ? (
              <li key={entry.key} className={entry.task.is_completed ? "is-complete" : ""}>
                <button
                  type="button"
                  className={`crm-task-check${entry.task.is_completed ? " checked" : ""}`}
                  aria-label={entry.task.is_completed ? `${entry.task.description} tamamlanmadı olarak işaretle` : `${entry.task.description} tamamlandı olarak işaretle`}
                  aria-pressed={Boolean(entry.task.is_completed)}
                  disabled={busy}
                  onClick={() => change(`/tasks/${entry.task.id}`, "PATCH", { is_completed: !entry.task.is_completed }, entry.task.is_completed ? "Görev yeniden açıldı." : "Görev tamamlandı.", "Görev güncellenemedi. Tekrar dene.")}
                >{entry.task.is_completed ? "✓" : ""}</button>
                <div>
                  <small>Görev · son tarih {displayDate(entry.date)}</small>
                  <p>{entry.task.description}</p>
                </div>
              </li>
            ) : (
              <li key={entry.key}>
                <span className="detail-timeline-dot" aria-hidden="true" />
                <div>
                  <small>{entry.activity.activity_type || "Aktivite"} · {displayDate(entry.date)}{entry.contactName ? ` · ${entry.contactName}` : ""}</small>
                  {entry.activity.notes && <p>{entry.activity.notes}</p>}
                </div>
              </li>
            ))}
          </ol>
        ) : <p className="muted">Henüz görev veya not yok. Aşağıdan ilkini ekleyebilirsin.</p>}
      </section>

      <div className="detail-forms">
        <QuickTaskForm busy={busy} onAdd={(task) => change("/tasks", "POST", { ...task, opportunity_id: id }, "Görev eklendi.", "Görev eklenemedi. Tekrar dene.")} />
        <QuickActivityForm contacts={contacts} busy={busy} onAdd={(activity) => change("/activities", "POST", { ...activity, opportunity_id: id }, "Not eklendi.", "Not eklenemedi. Tekrar dene.")} />
      </div>

      <EmailUpdatePanel
        api={api}
        token={token}
        opportunityId={id}
        currentStatus={opportunity.status}
        onApplied={(message) => { setNotice(message); setReloadKey((value) => value + 1); }}
      />
    </section>
  );
}

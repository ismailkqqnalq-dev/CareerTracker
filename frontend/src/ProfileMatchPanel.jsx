import { useCallback, useEffect, useState } from "react";

const PROFICIENCY_LEVELS = [
  ["beginner", "Başlangıç"],
  ["intermediate", "Orta"],
  ["advanced", "İleri"],
  ["expert", "Uzman"],
];

export default function ProfileMatchPanel({ api, token, skills }) {
  const [profileSkills, setProfileSkills] = useState([]);
  const [opportunities, setOpportunities] = useState([]);
  const [selectedSkillId, setSelectedSkillId] = useState("");
  const [newLevel, setNewLevel] = useState("beginner");
  const [newYears, setNewYears] = useState("0");
  const [drafts, setDrafts] = useState({});
  const [selectedOpportunityId, setSelectedOpportunityId] = useState("");
  const [requiredSkills, setRequiredSkills] = useState([]);
  const [selectedRequiredSkillId, setSelectedRequiredSkillId] = useState("");
  const [loadingRequiredSkills, setLoadingRequiredSkills] = useState(false);
  const [match, setMatch] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [profile, ownedOpportunities] = await Promise.all([
        api.requestAll("/users/me/skills", { token }),
        api.requestAll("/opportunities", { token }),
      ]);
      setProfileSkills(profile);
      setOpportunities(ownedOpportunities);
      setDrafts(Object.fromEntries(profile.map((item) => [item.id, {
        proficiency_level: item.proficiency_level,
        years_experience: String(item.years_experience),
      }])));
    } catch (loadError) {
      if (loadError.status !== 401) setError("Profil bilgileri yüklenemedi. Tekrar deneyebilirsin.");
    } finally {
      setLoading(false);
    }
  }, [api, token]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (!selectedOpportunityId) {
      setRequiredSkills([]);
      setMatch(null);
      return undefined;
    }
    let active = true;
    setLoadingRequiredSkills(true);
    api.request(`/opportunities/${selectedOpportunityId}/skills`, { token })
      .then((items) => { if (active) setRequiredSkills(items); })
      .catch((loadError) => {
        if (active && loadError.status !== 401) setError("Fırsatın becerileri yüklenemedi.");
      })
      .finally(() => { if (active) setLoadingRequiredSkills(false); });
    return () => { active = false; };
  }, [api, token, selectedOpportunityId]);

  async function addProfileSkill(event) {
    event.preventDefault();
    if (!selectedSkillId) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const created = await api.request("/users/me/skills", {
        method: "POST",
        token,
        body: JSON.stringify({
          skill_id: Number(selectedSkillId),
          proficiency_level: newLevel,
          years_experience: Number(newYears),
        }),
      });
      setProfileSkills((current) => [...current, created]);
      setDrafts((current) => ({
        ...current,
        [created.id]: {
          proficiency_level: created.proficiency_level,
          years_experience: String(created.years_experience),
        },
      }));
      setSelectedSkillId("");
      setNewLevel("beginner");
      setNewYears("0");
      setNotice("Beceri profiline eklendi.");
    } catch (saveError) {
      if (saveError.status !== 401) setError("Beceri profile eklenemedi. Zaten ekli olabilir.");
    } finally {
      setBusy(false);
    }
  }

  function updateDraft(profileSkillId, field, value) {
    setDrafts((current) => ({
      ...current,
      [profileSkillId]: { ...current[profileSkillId], [field]: value },
    }));
  }

  async function saveProfileSkill(profileSkill) {
    const draft = drafts[profileSkill.id];
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const updated = await api.request(`/users/me/skills/${profileSkill.id}`, {
        method: "PATCH",
        token,
        body: JSON.stringify({
          proficiency_level: draft.proficiency_level,
          years_experience: Number(draft.years_experience),
        }),
      });
      setProfileSkills((current) => current.map((item) => item.id === updated.id ? updated : item));
      setNotice("Profil becerisi güncellendi.");
    } catch (saveError) {
      if (saveError.status !== 401) setError("Profil becerisi güncellenemedi. Bilgileri kontrol et.");
    } finally {
      setBusy(false);
    }
  }

  async function removeProfileSkill(profileSkill) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.request(`/users/me/skills/${profileSkill.id}`, { method: "DELETE", token });
      setProfileSkills((current) => current.filter((item) => item.id !== profileSkill.id));
      setDrafts((current) => Object.fromEntries(Object.entries(current).filter(([id]) => Number(id) !== profileSkill.id)));
      setNotice("Beceri profilinden kaldırıldı.");
    } catch (deleteError) {
      if (deleteError.status !== 401) setError("Beceri profilden kaldırılamadı. Tekrar deneyebilirsin.");
    } finally {
      setBusy(false);
    }
  }

  async function calculateMatch(event) {
    event.preventDefault();
    if (!selectedOpportunityId) return;
    setBusy(true);
    setError("");
    setNotice("");
    setMatch(null);
    try {
      const result = await api.request(`/opportunities/${selectedOpportunityId}/skill-match`, { token });
      setMatch(result);
    } catch (matchError) {
      if (matchError.status !== 401) setError("Fırsat eşleşmesi alınamadı. Fırsatı yenileyip tekrar dene.");
    } finally {
      setBusy(false);
    }
  }

  async function addOpportunitySkill(event) {
    event.preventDefault();
    const skill = skills.find((item) => item.id === Number(selectedRequiredSkillId));
    if (!selectedOpportunityId || !skill) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const added = await api.request(`/opportunities/${selectedOpportunityId}/skills`, {
        method: "POST",
        token,
        body: JSON.stringify({ skill: skill.name }),
      });
      setRequiredSkills((current) => current.some((item) => item.id === added.id) ? current : [...current, added]);
      setSelectedRequiredSkillId("");
      setMatch(null);
      setNotice("Beceri fırsatın gereksinimlerine eklendi.");
    } catch (addError) {
      if (addError.status !== 401) setError("Beceri fırsata eklenemedi. Zaten ekli olabilir.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="profile-match-layout">
      {error && <p className="form-error" role="alert">{error}</p>}
      {notice && <p className="notice" role="status">{notice}</p>}

      <section className="analysis-card" aria-labelledby="profile-skills-title">
        <div className="analysis-heading">
          <h2 id="profile-skills-title">Profil becerilerim</h2>
          <p className="muted">Becerilerini ve deneyim düzeyini kişisel profiline ekle.</p>
        </div>
        <form className="profile-skill-form" onSubmit={addProfileSkill}>
          <label htmlFor="profile-skill">Yeni profil becerisi</label>
          <select id="profile-skill" required value={selectedSkillId} onChange={(event) => setSelectedSkillId(event.target.value)}>
            <option value="">Beceri seç</option>
            {skills.filter((skill) => !profileSkills.some((item) => item.skill_id === skill.id)).map((skill) => (
              <option key={skill.id} value={skill.id}>{skill.name}</option>
            ))}
          </select>
          <label htmlFor="new-profile-level">Yetkinlik seviyesi</label>
          <select id="new-profile-level" value={newLevel} onChange={(event) => setNewLevel(event.target.value)}>
            {PROFICIENCY_LEVELS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <label htmlFor="new-profile-years">Yıl deneyim</label>
          <input id="new-profile-years" type="number" min="0" step="0.5" value={newYears} onChange={(event) => setNewYears(event.target.value)} />
          <button className="button button-primary" disabled={busy || !selectedSkillId}>Profile ekle</button>
        </form>

        {loading ? <p>Profil becerileri yükleniyor…</p> : profileSkills.length === 0 ? (
          <p className="profile-empty">Henüz profil becerisi eklemedin.</p>
        ) : (
          <ul className="profile-skill-list" aria-label="Profil becerilerim listesi">
            {profileSkills.map((profileSkill) => {
              const skill = skills.find((item) => item.id === profileSkill.skill_id);
              const name = skill?.name || `Beceri #${profileSkill.skill_id}`;
              const draft = drafts[profileSkill.id] || {
                proficiency_level: profileSkill.proficiency_level,
                years_experience: String(profileSkill.years_experience),
              };
              return (
                <li key={profileSkill.id} className="profile-skill-row">
                  <strong>{name}</strong>
                  <label htmlFor={`level-${profileSkill.id}`}>{name} yetkinlik seviyesi</label>
                  <select id={`level-${profileSkill.id}`} value={draft.proficiency_level} onChange={(event) => updateDraft(profileSkill.id, "proficiency_level", event.target.value)}>
                    {PROFICIENCY_LEVELS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                  <label htmlFor={`years-${profileSkill.id}`}>{name} yıl deneyimi</label>
                  <input id={`years-${profileSkill.id}`} type="number" min="0" step="0.5" value={draft.years_experience} onChange={(event) => updateDraft(profileSkill.id, "years_experience", event.target.value)} />
                  <button className="button button-quiet" disabled={busy} onClick={() => saveProfileSkill(profileSkill)}> {name} kaydet</button>
                  <button className="text-button" disabled={busy} onClick={() => removeProfileSkill(profileSkill)}>{name} profilinden kaldır</button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="analysis-card" aria-labelledby="opportunity-match-title">
        <div className="analysis-heading">
          <h2 id="opportunity-match-title">Fırsat beceri eşleşmesi</h2>
          <p className="muted">Bir fırsatı seçerek gereken becerilerle profilini karşılaştır.</p>
          <p className="analysis-privacy">Yüzde, fırsata eklenmiş beceriler içinde profilde bulunanların oranıdır; işe alınma olasılığı değildir.</p>
        </div>
        <form className="opportunity-match-form" onSubmit={calculateMatch}>
          <label htmlFor="match-opportunity">Fırsat seç</label>
          <select id="match-opportunity" value={selectedOpportunityId} onChange={(event) => setSelectedOpportunityId(event.target.value)}>
            <option value="">Fırsat seç</option>
            {opportunities.map((opportunity) => <option key={opportunity.id} value={opportunity.id}>#{opportunity.id} · {opportunity.company} — {opportunity.position}</option>)}
          </select>
          <button className="button button-primary" disabled={busy || loading || loadingRequiredSkills || !selectedOpportunityId}>Eşleşmeyi hesapla</button>
        </form>
        {selectedOpportunityId && (
          <>
            <form className="opportunity-skill-form" onSubmit={addOpportunitySkill}>
              <label htmlFor="required-skill">Fırsat becerisi ekle</label>
              <select id="required-skill" value={selectedRequiredSkillId} onChange={(event) => setSelectedRequiredSkillId(event.target.value)}>
                <option value="">Katalogdan beceri seç</option>
                {skills.filter((skill) => !requiredSkills.some((required) => required.id === skill.id)).map((skill) => <option key={skill.id} value={skill.id}>{skill.name}</option>)}
              </select>
              <button className="button button-quiet" disabled={busy || loadingRequiredSkills || !selectedRequiredSkillId}>Gerekli beceri ekle</button>
            </form>
            <div className="required-skills" aria-live="polite">
              <h3>Fırsatın beceri gereksinimleri</h3>
              {loadingRequiredSkills ? <p>Gereksinimler yükleniyor…</p> : requiredSkills.length ? <ul>{requiredSkills.map((skill) => <li key={skill.id}>{skill.name}</li>)}</ul> : <p>Henüz beceri gereksinimi yok.</p>}
            </div>
          </>
        )}
        {!loading && opportunities.length === 0 && <p className="profile-empty">Eşleştirme için önce bir fırsat ekle.</p>}
        {match && (
          <div className="analysis-results" aria-live="polite">
            <h3>Eşleşme sonucu</h3>
            <p className="analysis-role"><strong>%{match.match_percentage} eşleşme</strong> · {match.matched_skill_count}/{match.required_skill_count} beceri</p>
            <div className="match-result-columns">
              <div><h4>Profilinde bulunan</h4>{match.matched_skills.length ? <ul>{match.matched_skills.map((skill) => <li key={skill.id}><strong>{skill.name}</strong></li>)}</ul> : <p>Henüz eşleşen beceri yok.</p>}</div>
              <div><h4>Eksik beceriler</h4>{match.missing_skills.length ? <ul>{match.missing_skills.map((skill) => <li key={skill.id}><strong>{skill.name}</strong></li>)}</ul> : <p>Eksik beceri yok.</p>}</div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

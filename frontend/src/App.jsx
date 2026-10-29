import { useCallback, useEffect, useMemo, useState } from "react";
import { createApiClient } from "./api.js";

const authApi = createApiClient();

function errorMessage(error, context = "İstek") {
  if (error.errorCode === "skill_already_recognized") {
    return "Bu beceri zaten katalogda tanınıyor. Mevcut beceriyi kullanabilirsin.";
  }
  if (error.errorCode === "job_text_too_large") {
    return "İlan metni 100 KB sınırını aşıyor. Daha kısa bir metin deneyin.";
  }
  if (error.errorCode === "invalid_job_text") {
    return "İlan metni okunamadı. Metni kontrol edip tekrar deneyin.";
  }
  if (error.status === 401 && context === "Giriş") {
    return "E-posta veya şifre geçersiz.";
  }
  if (error.status === 409 && context === "Kayıt") {
    return "Bu e-posta ile bir hesap zaten bulunuyor.";
  }
  return `${context} tamamlanamadı. Lütfen tekrar dene.`;
}

function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "register") {
        await authApi.request("/auth/register", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
      }
      const form = new URLSearchParams({ username: email, password });
      const result = await authApi.request("/auth/token", {
        method: "POST",
        body: form,
      });
      onAuthenticated(result.access_token);
    } catch (submitError) {
      setError(errorMessage(submitError, mode === "login" ? "Giriş" : "Kayıt"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-layout">
      <section className="auth-card">
        <Brand />
        <p className="eyebrow">BECERİ KATALOĞU</p>
        <h1>{mode === "login" ? "Hesabına giriş yap" : "Hesabını oluştur"}</h1>
        <p className="muted">Bekleyen beceri önerilerini inceleyip doğru beceriyle eşleştir.</p>
        <form className="auth-form" onSubmit={submit}>
          <label htmlFor="email">E-posta</label>
          <input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          <label htmlFor="password">Şifre</label>
          <input id="password" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={8} required value={password} onChange={(e) => setPassword(e.target.value)} />
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="button button-primary full-width" disabled={busy}>
            {busy ? "İşleniyor…" : mode === "login" ? "Giriş yap" : "Kayıt ol"}
          </button>
        </form>
        <p className="auth-switch">
          {mode === "login" ? "Hesabın yok mu?" : "Zaten hesabın var mı?"}{" "}
          <button className="text-button" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
            {mode === "login" ? "Kayıt ol" : "Giriş yap"}
          </button>
        </p>
      </section>
    </main>
  );
}

function Brand() {
  return <div className="brand"><span className="brand-mark">C</span><span>Career<span className="brand-accent">Tracker</span></span></div>;
}

function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem("careertracker_token"));
  const [user, setUser] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [skills, setSkills] = useState([]);
  const [candidates, setCandidates] = useState({});
  const [selected, setSelected] = useState({});
  const [search, setSearch] = useState({});
  const [loading, setLoading] = useState(false);
  const [resolving, setResolving] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [newSkill, setNewSkill] = useState("");
  const [submittingSuggestion, setSubmittingSuggestion] = useState(false);
  const [jobText, setJobText] = useState("");
  const [jobAnalysis, setJobAnalysis] = useState(null);
  const [analyzingJob, setAnalyzingJob] = useState(false);

  const logout = useCallback(() => {
    sessionStorage.removeItem("careertracker_token");
    setToken(null);
    setUser(null);
    setSuggestions([]);
  }, []);

  const api = useMemo(() => createApiClient({ onUnauthorized: logout }), [logout]);

  const load = useCallback(async (authToken) => {
    setLoading(true);
    setError("");
    try {
      const [me, pending, catalog] = await Promise.all([
        api.request("/auth/me", { token: authToken }),
        api.request("/skills/suggestions?status=pending", { token: authToken }),
        api.request("/skills", { token: authToken }),
      ]);
      setUser(me);
      setSuggestions(pending);
      setSkills(catalog);
      const ranked = await Promise.all(pending.map(async (suggestion) => {
        const options = await api.request(`/skills/suggestions/${suggestion.id}/candidates?limit=5`, { token: authToken });
        return [suggestion.id, options];
      }));
      setCandidates(Object.fromEntries(ranked));
      setSelected((current) => {
        const valid = new Set(pending.map((item) => item.id));
        return Object.fromEntries(Object.entries(current).filter(([id]) => valid.has(Number(id))));
      });
    } catch (loadError) {
      if (loadError.status !== 401) setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    if (!token) return;
    sessionStorage.setItem("careertracker_token", token);
    load(token);
  }, [token, load]);

  const pendingCount = suggestions.length;
  const filteredSkills = useMemo(() => {
    return Object.fromEntries(suggestions.map((suggestion) => {
      const query = (search[suggestion.id] || "").trim().toLocaleLowerCase("tr");
      const skillId = selected[suggestion.id];
      const candidateIds = new Set((candidates[suggestion.id] || []).map((item) => item.id));
      const options = skills.filter((skill) => {
        if (query) return skill.name.toLocaleLowerCase("tr").includes(query);
        return candidateIds.has(skill.id);
      });
      return [suggestion.id, options];
    }));
  }, [candidates, search, selected, skills, suggestions]);

  async function mapSuggestion(suggestion) {
    const skillId = selected[suggestion.id];
    if (!skillId) return;
    setResolving(suggestion.id);
    setError("");
    setNotice("");
    try {
      const result = await api.request(`/skills/suggestions/${suggestion.id}`, {
        method: "PATCH",
        token,
        body: JSON.stringify({ skill_id: Number(skillId) }),
      });
      if (result.status !== "accepted") {
        setError("Eşleştirme beklenen durumu döndürmedi. Öneri durumunu yenile.");
        return;
      }
      setNotice(`“${suggestion.raw_name}” becerisi eşleştirildi.`);
      await load(token);
    } catch (resolveError) {
      if (resolveError.status !== 401) setError(errorMessage(resolveError));
    } finally {
      setResolving(null);
    }
  }

  async function submitSuggestion(event) {
    event.preventDefault();
    const skill = newSkill.trim();
    if (!skill) return;
    setSubmittingSuggestion(true);
    setError("");
    setNotice("");
    try {
      const result = await api.request("/skills/suggestions", {
        method: "POST",
        token,
        body: JSON.stringify({ skill }),
      });
      if (result.status === "pending") {
        setNewSkill("");
        setNotice(`“${result.raw_name}” bekleyen önerilere eklendi.`);
        await load(token);
      } else if (result.status === "accepted" && result.resolved_skill_id == null) {
        setNewSkill("");
        setNotice("Bu öneri daha önce kabul edilmiş, ancak hedef beceri artık mevcut değil. Yeni bir eşleştirme gerekiyor.");
      } else if (result.status === "accepted") {
        setNewSkill("");
        setNotice("Bu beceri önerisi daha önce kabul edilmiş ve eşleştirilmiş.");
      } else {
        setError("Beceri önerisi beklenmeyen bir durumla döndü. Tekrar deneyebilirsin.");
      }
    } catch (submitError) {
      if (
        submitError.status === 409 &&
        submitError.errorCode === "skill_already_recognized"
      ) {
        try {
          const recognizedSkill = await api.request(
            `/skills/resolve?name=${encodeURIComponent(skill)}`,
            { token },
          );
          if (recognizedSkill?.name) {
            setError(
              `Bu beceri katalogda "${recognizedSkill.name}" olarak tanınıyor. Mevcut beceriyi kullanabilirsin.`,
            );
            return;
          }
        } catch (resolveError) {
          if (resolveError.status === 401) return;
        }
        setError(errorMessage(submitError));
      } else if (submitError.status !== 401) {
        setError(errorMessage(submitError));
      }
    } finally {
      setSubmittingSuggestion(false);
    }
  }

  async function analyzeJobText(event) {
    event.preventDefault();
    if (!jobText.trim()) return;
    setAnalyzingJob(true);
    setJobAnalysis(null);
    setError("");
    setNotice("");
    try {
      const result = await api.request("/job-analysis", {
        method: "POST",
        token,
        body: JSON.stringify({ text: jobText }),
      });
      setJobAnalysis(result);
    } catch (analysisError) {
      if (analysisError.status !== 401) setError(errorMessage(analysisError, "İlan metni analizi"));
    } finally {
      setAnalyzingJob(false);
    }
  }

  if (!token) return <AuthScreen onAuthenticated={setToken} />;

  return (
    <div className="app-shell">
      <header className="topbar">
        <Brand />
        <div className="account"><span className="account-email">{user?.email || ""}</span><button className="button button-quiet" onClick={logout}>Çıkış yap</button></div>
      </header>

      <main className="page-content">
        <div className="page-heading">
          <div>
            <p className="eyebrow">KİŞİSEL BECERİ KATALOĞUN</p>
            <h1>Beceri önerileri</h1>
            <p className="muted heading-copy">Sistemin tanımadığı becerileri mevcut katalogdaki doğru beceriyle eşleştir.</p>
          </div>
          <div className="count-card"><span className="count-number">{pendingCount}</span><span>bekleyen öneri</span></div>
        </div>

        <section className="analysis-card" aria-labelledby="job-analysis-title">
          <div className="analysis-heading">
            <h2 id="job-analysis-title">İlan metnini analiz et</h2>
            <p className="muted">İlan metnini yapıştır. Bulunan beceriler, yalnızca kendi katalog ve eşleştirmelerinle karşılaştırılır.</p>
            <p className="analysis-privacy">Metin saklanmaz. Eşleştirme kural tabanlıdır; yapay zekâ veya doğruluk olasılığı değildir.</p>
          </div>
          <form className="analysis-form" onSubmit={analyzeJobText}>
            <label htmlFor="job-text">İlan metni</label>
            <textarea
              id="job-text"
              maxLength={100_000}
              rows={6}
              value={jobText}
              onChange={(event) => setJobText(event.target.value)}
              placeholder="OCR sonucunu veya ilan metnini buraya yapıştır…"
            />
            <button className="button button-primary" disabled={analyzingJob || !jobText.trim()}>
              {analyzingJob ? "Analiz ediliyor…" : "Metni analiz et"}
            </button>
          </form>
          {jobAnalysis && (
            <section className="analysis-results" aria-live="polite">
              <h3>Bulunan beceriler</h3>
              {jobAnalysis.role && <p className="analysis-role">Açıkça belirtilen rol: <strong>{jobAnalysis.role}</strong></p>}
              {jobAnalysis.skills.length ? (
                <ul>
                  {jobAnalysis.skills.map((skill) => (
                    <li key={skill.skill_id}>
                      <strong>{skill.name}</strong>
                      <span>{skill.category || "Kategori belirtilmemiş"}</span>
                      {skill.occurrences.map((occurrence, index) => (
                        <small key={`${skill.skill_id}-${occurrence.line_number}-${index}`}>
                          {occurrence.section === "required" ? "Zorunlu bölüm" : occurrence.section === "preferred" ? "Tercih bölümü" : "Belirtilmemiş bölüm"} · satır {occurrence.line_number}
                        </small>
                      ))}
                    </li>
                  ))}
                </ul>
              ) : <p>Kişisel katalogda eşleşen beceri bulunamadı.</p>}
            </section>
          )}
        </section>

        <section className="suggestion-input-card" aria-labelledby="suggestion-input-title">
          <div>
            <h2 id="suggestion-input-title">Listede olmayan bir beceri mi var?</h2>
            <p className="muted">Beceri adını gönder; kişisel eşleştirme için önerilerine eklensin.</p>
          </div>
          <form className="suggestion-input-form" onSubmit={submitSuggestion}>
            <label htmlFor="new-skill">Beceri adı</label>
            <div className="suggestion-input-row">
              <input id="new-skill" name="skill" maxLength={120} required value={newSkill} onChange={(event) => setNewSkill(event.target.value)} placeholder="Örn. React, PostgreSQL, Python" />
              <button className="button button-primary" disabled={submittingSuggestion || !newSkill.trim()}>
                {submittingSuggestion ? "Gönderiliyor…" : "Öneri gönder"}
              </button>
            </div>
          </form>
        </section>

        {notice && <div className="notice" role="status">{notice}</div>}
        {error && <div className="alert" role="alert"><span>{error}</span><button className="text-button" onClick={() => setError("")}>Kapat</button></div>}

        {loading ? (
          <div className="empty-state"><span className="loader" /><p>Öneriler yükleniyor…</p></div>
        ) : pendingCount === 0 ? (
          <section className="empty-state"><div className="empty-icon">✓</div><h2>Hepsi güncel</h2><p>Şu anda eşleştirilmeyi bekleyen beceri önerin yok.</p></section>
        ) : (
          <section className="suggestion-list" aria-label="Bekleyen beceri önerileri">
            {suggestions.map((suggestion) => {
              const options = filteredSkills[suggestion.id] || [];
              const selectedSkill = skills.find((skill) => skill.id === Number(selected[suggestion.id]));
              return (
                <article className="suggestion-card" key={suggestion.id}>
                  <div className="suggestion-topline">
                    <div><span className="status-pill"><span /> İnceleme bekliyor</span><h2>{suggestion.raw_name}</h2><p className="normalized">Normalize edilmiş ad: <code>{suggestion.normalized_name}</code></p></div>
                    <time dateTime={suggestion.created_at}>{new Intl.DateTimeFormat("tr-TR", { dateStyle: "medium" }).format(new Date(suggestion.created_at))}</time>
                  </div>

                  <div className="mapping-area">
                    <div className="mapping-heading"><div><h3>Hangi beceriyle eşleşiyor?</h3><p className="muted">Önerilenlerden seç veya katalogda ara. Eşleştirme yalnızca senin hesabın için geçerlidir.</p></div></div>
                    {(candidates[suggestion.id] || []).length > 0 && !search[suggestion.id] && <p className="recommendation-label">Yakın eşleşmeler</p>}
                    <div className="candidate-list">
                      {options.slice(0, 5).map((skill) => {
                        const ranked = (candidates[suggestion.id] || []).find((item) => item.id === skill.id);
                        const isSelected = Number(selected[suggestion.id]) === skill.id;
                        return <button type="button" key={skill.id} className={`candidate-option ${isSelected ? "selected" : ""}`} onClick={() => setSelected((current) => ({ ...current, [suggestion.id]: skill.id }))}>
                          <span className="radio-mark">{isSelected && <span />}</span><span className="candidate-name">{skill.name}<small>{skill.category || "Kategori belirtilmemiş"}</small></span>{ranked && <span className="match-score">{Math.round(ranked.score * 100)}% yakın</span>}
                        </button>;
                      })}
                      {!search[suggestion.id] && options.length === 0 && <p className="no-candidates">Yakın bir eşleşme bulamadık. Katalogda arama yapabilirsin.</p>}
                    </div>
                    <label className="search-label" htmlFor={`catalog-${suggestion.id}`}>Katalogda başka beceri ara</label>
                    <input id={`catalog-${suggestion.id}`} className="catalog-search" type="search" placeholder="Örn. React, PostgreSQL, Python" value={search[suggestion.id] || ""} onChange={(e) => { setSearch((current) => ({ ...current, [suggestion.id]: e.target.value })); setSelected((current) => ({ ...current, [suggestion.id]: "" })); }} />
                    {search[suggestion.id] && <div className="search-results" role="listbox" aria-label="Katalog becerileri">
                      {options.length ? options.slice(0, 8).map((skill) => <button key={skill.id} role="option" aria-selected={Number(selected[suggestion.id]) === skill.id} onClick={() => { setSelected((current) => ({ ...current, [suggestion.id]: skill.id })); setSearch((current) => ({ ...current, [suggestion.id]: "" })); }}>{skill.name}<span>{skill.category || ""}</span></button>) : <p>Bu aramayla eşleşen beceri bulunamadı.</p>}
                    </div>}
                    <div className="card-actions"><span className="selection-summary">{selectedSkill ? <>Seçilen: <strong>{selectedSkill.name}</strong></> : "Eşleştirme seçilmedi"}</span><button className="button button-primary" disabled={!selectedSkill || resolving === suggestion.id} onClick={() => mapSuggestion(suggestion)}>{resolving === suggestion.id ? "Eşleştiriliyor…" : "Eşleştirmeyi onayla"}</button></div>
                  </div>
                </article>
              );
            })}
          </section>
        )}
        <p className="privacy-note"><span>🔒</span> Beceri eşleştirmelerin kişiseldir; genel skill kataloğuna otomatik alias eklenmez.</p>
      </main>
    </div>
  );
}

export default App;

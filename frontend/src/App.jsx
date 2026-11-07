import { useCallback, useEffect, useMemo, useState } from "react";
import { createApiClient } from "./api.js";
import ProfileMatchPanel from "./ProfileMatchPanel.jsx";
import ApplicationAnalyticsPanel from "./ApplicationAnalyticsPanel.jsx";
import JobAnalysisResults from "./JobAnalysisResults.jsx";
import CrmWorkspace, { VIEW_TITLES } from "./CrmWorkspace.jsx";

const authApi = createApiClient();
const MAX_OCR_IMAGE_BYTES = 10 * 1024 * 1024;
const OCR_IMAGE_TYPES = new Set(["image/png", "image/jpeg"]);

function errorMessage(error, context = "İstek") {
  if (context === "Kayıt" && error.errorCode === "registration_disabled") {
    return "Kayıtlar şu anda kapalı.";
  }
  if (error.errorCode === "skill_already_recognized") {
    return "Bu beceri zaten katalogda tanınıyor. Mevcut beceriyi kullanabilirsin.";
  }
  if (error.errorCode === "job_text_too_large") {
    return "İlan metni 100 KB sınırını aşıyor. Daha kısa bir metin deneyin.";
  }
  if (error.errorCode === "invalid_job_text") {
    return "İlan metni okunamadı. Metni kontrol edip tekrar deneyin.";
  }
  if (error.errorCode === "image_too_large") {
    return "Görsel 10 MiB sınırını aşıyor.";
  }
  if (error.errorCode === "unsupported_image_type") {
    return "Yalnızca PNG veya JPEG görselleri yükleyebilirsin.";
  }
  if (error.errorCode === "invalid_image" || error.errorCode === "empty_image") {
    return "Görsel okunamadı. Geçerli ve boş olmayan bir PNG veya JPEG seç.";
  }
  if (error.errorCode === "ocr_engine_unavailable" || error.errorCode === "ocr_engine_initialization_failed") {
    return "OCR motoru şu anda kullanılamıyor. Lütfen daha sonra tekrar dene.";
  }
  if (error.errorCode === "ocr_busy" || error.errorCode === "rate_limited") {
    return "OCR isteği şu anda işlenemiyor. Biraz bekleyip tekrar dene.";
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
  const [jobImage, setJobImage] = useState(null);
  const [ocrResult, setOcrResult] = useState(null);
  const [extractingText, setExtractingText] = useState(false);
  const [activeView, setActiveView] = useState("suggestions");

  const logout = useCallback(() => {
    sessionStorage.removeItem("careertracker_token");
    setToken(null);
    setUser(null);
    setSuggestions([]);
    setJobImage(null);
    setOcrResult(null);
  }, []);

  const api = useMemo(() => createApiClient({ onUnauthorized: logout }), [logout]);

  const load = useCallback(async (authToken) => {
    setLoading(true);
    setError("");
    try {
      const [me, pending, catalog] = await Promise.all([
        api.request("/auth/me", { token: authToken }),
        api.requestAll("/skills/suggestions?status=pending", { token: authToken }),
        api.requestAll("/skills", { token: authToken }),
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

  function selectJobImage(event) {
    const file = event.target.files?.[0] || null;
    setJobImage(file);
    setOcrResult(null);
    setError("");
    setNotice("");
    if (!file) return;
    if (!OCR_IMAGE_TYPES.has(file.type)) {
      setError("Yalnızca PNG veya JPEG görselleri yükleyebilirsin.");
    } else if (file.size > MAX_OCR_IMAGE_BYTES) {
      setError("Görsel 10 MiB sınırını aşıyor.");
    }
  }

  async function extractImageText(event) {
    event.preventDefault();
    if (!jobImage || !OCR_IMAGE_TYPES.has(jobImage.type) || jobImage.size > MAX_OCR_IMAGE_BYTES) return;
    setExtractingText(true);
    setOcrResult(null);
    setError("");
    setNotice("");
    try {
      const result = await api.request("/ocr/extract", {
        method: "POST",
        token,
        headers: { "Content-Type": jobImage.type },
        body: jobImage,
      });
      setOcrResult(result);
      setNotice(result.text.trim()
        ? "Görseldeki metin çıkarıldı. İstersen ilan analizine aktarabilirsin."
        : "Görsel işlendi ancak okunabilir metin bulunamadı.");
    } catch (ocrError) {
      if (ocrError.status !== 401) setError(errorMessage(ocrError, "Görselden metin çıkarma"));
    } finally {
      setExtractingText(false);
    }
  }

  function useExtractedText() {
    if (!ocrResult?.text.trim()) return;
    setJobText(ocrResult.text);
    setJobAnalysis(null);
    setNotice("Çıkarılan metin ilan analizi alanına aktarıldı.");
  }

  if (!token) return <AuthScreen onAuthenticated={setToken} />;

  return (
    <div className="app-shell">
      <header className="topbar">
        <Brand />
        <div className="account"><span className="account-email">{user?.email || ""}</span><button className="button button-quiet" onClick={logout}>Çıkış yap</button></div>
      </header>

      <main className="page-content">
        <div className="app-workspace-layout">
          <nav className="app-section-nav" aria-label="CareerTracker bölümleri">
            <p className="nav-group-label">ÇALIŞMA ALANI</p>
            {[["overview", "Genel bakış"], ["opportunities", "Başvurular"], ["contacts", "Kişiler"], ["tasks", "Görevler"], ["activities", "Aktiviteler"]].map(([view, label]) => (
              <button key={view} type="button" aria-current={activeView === view ? "page" : undefined} onClick={() => setActiveView(view)}><span className="nav-icon" aria-hidden="true">{({ overview: "⌂", opportunities: "▣", contacts: "♧", tasks: "✓", activities: "◷" })[view]}</span>{label}</button>
            ))}
            <p className="nav-group-label nav-group-secondary">BECERİ VE ANALİZ</p>
            <button type="button" aria-current={activeView === "suggestions" ? "page" : undefined} onClick={() => setActiveView("suggestions")}><span className="nav-icon" aria-hidden="true">✧</span>Beceri önerileri</button>
            <button type="button" aria-current={activeView === "profile" ? "page" : undefined} onClick={() => setActiveView("profile")}><span className="nav-icon" aria-hidden="true">◎</span>Profil ve eşleşme</button>
            <button type="button" aria-current={activeView === "analytics" ? "page" : undefined} onClick={() => setActiveView("analytics")}><span className="nav-icon" aria-hidden="true">▤</span>Başvuru analizi</button>
          </nav>

          <div className="app-main-view">
        <div className="page-heading">
          <div>
            <p className="eyebrow">{VIEW_TITLES[activeView] ? "KİŞİSEL ÇALIŞMA ALANIN" : "BECERİ VE İLAN MERKEZİ"}</p>
            <h1>{VIEW_TITLES[activeView] || (activeView === "suggestions" ? "Beceri önerileri" : activeView === "profile" ? "Profil ve fırsat eşleşmesi" : "Başvuru analizi")}</h1>
            <p className="muted heading-copy">{VIEW_TITLES[activeView] ? "Kariyer sürecini düzenle ve takip adımlarını yönet." : activeView === "suggestions" ? "Sistemin tanımadığı becerileri eşleştir, ilan metnini incele ve beceri analizini kullan." : activeView === "profile" ? "Profil becerilerini yönet ve kendi fırsatlarınla karşılaştır." : "Başvurularının aylara göre dağılımını incele."}</p>
          </div>
          {activeView === "suggestions" && <div className="count-card"><span className="count-number">{pendingCount}</span><span>bekleyen öneri</span></div>}
        </div>

        {VIEW_TITLES[activeView] ? (
          <CrmWorkspace api={api} token={token} view={activeView} onNavigate={setActiveView} />
        ) : activeView === "analytics" ? (
          <ApplicationAnalyticsPanel api={api} token={token} />
        ) : activeView === "profile" ? (
          <ProfileMatchPanel api={api} token={token} skills={skills} />
        ) : (
          <>
        <section className="ocr-card" aria-labelledby="ocr-title">
          <div className="ocr-heading">
            <h2 id="ocr-title">İlan görselinden metin çıkar</h2>
            <p className="muted">PNG veya JPEG, en fazla 10 MiB. Görsel ve OCR sonucu sunucuda saklanmaz.</p>
          </div>
          <form className="ocr-form" onSubmit={extractImageText}>
            <label htmlFor="job-image">İlan görseli</label>
            <input
              id="job-image"
              type="file"
              accept="image/png,image/jpeg"
              disabled={extractingText}
              onChange={selectJobImage}
            />
            <button
              className="button button-primary"
              disabled={!jobImage || !OCR_IMAGE_TYPES.has(jobImage.type) || jobImage.size > MAX_OCR_IMAGE_BYTES || extractingText}
            >
              {extractingText ? "Metin çıkarılıyor…" : "Görselden metin çıkar"}
            </button>
          </form>
          {ocrResult && (
            <div className="ocr-result" aria-live="polite">
              <label htmlFor="ocr-text">Çıkarılan metin</label>
              <textarea id="ocr-text" readOnly rows={5} value={ocrResult.text} />
              <div className="ocr-result-footer">
                <span>{ocrResult.image_format} · {ocrResult.width} × {ocrResult.height}</span>
                <button
                  className="button button-quiet"
                  type="button"
                  disabled={!ocrResult.text.trim()}
                  onClick={useExtractedText}
                >
                  Analiz alanına aktar
                </button>
              </div>
            </div>
          )}
        </section>

        <section className="analysis-card" aria-labelledby="job-analysis-title">
          <div className="analysis-heading">
            <h2 id="job-analysis-title">İlan metnini analiz et</h2>
            <p className="muted">İlan metnini yapıştır. Yalnızca katalogda tanınan beceriler bulunur; katalog dışındaki beceriler görünmeyebilir. OCR metnini analiz etmeden önce kontrol et.</p>
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
          {jobAnalysis && <JobAnalysisResults result={jobAnalysis} />}
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
          </>
        )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;

import { useState } from "react";

const MIN_PASSWORD_LENGTH = 8;

function failureMessage(error, action) {
  if (error.errorCode === "password_confirmation_failed") return "Mevcut şifre yanlış.";
  if (error.status === 422) return `Şifre en az ${MIN_PASSWORD_LENGTH}, en fazla 128 karakter olmalı.`;
  return `${action} tamamlanamadı. Lütfen tekrar dene.`;
}

function ChangePasswordForm({ api, token }) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [repeatPassword, setRepeatPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function submit(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    if (newPassword !== repeatPassword) {
      setError("Yeni şifreler birbirini tutmuyor.");
      return;
    }
    setBusy(true);
    try {
      await api.request("/auth/me/password", {
        method: "POST",
        token,
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      setCurrentPassword("");
      setNewPassword("");
      setRepeatPassword("");
      setNotice("Şifren değiştirildi. Bir sonraki girişte yeni şifreni kullan.");
    } catch (submitError) {
      if (submitError.status !== 401) setError(failureMessage(submitError, "Şifre değiştirme"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="account-card" aria-labelledby="change-password-title">
      <h2 id="change-password-title">Şifreyi değiştir</h2>
      <form className="account-form" onSubmit={submit}>
        <label htmlFor="current-password">Mevcut şifre</label>
        <input id="current-password" type="password" autoComplete="current-password" required minLength={MIN_PASSWORD_LENGTH} value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} />
        <label htmlFor="new-password">Yeni şifre</label>
        <input id="new-password" type="password" autoComplete="new-password" required minLength={MIN_PASSWORD_LENGTH} maxLength={128} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
        <label htmlFor="repeat-password">Yeni şifre (tekrar)</label>
        <input id="repeat-password" type="password" autoComplete="new-password" required minLength={MIN_PASSWORD_LENGTH} maxLength={128} value={repeatPassword} onChange={(event) => setRepeatPassword(event.target.value)} />
        {error && <p className="form-error" role="alert">{error}</p>}
        {notice && <p className="notice" role="status">{notice}</p>}
        <button className="button button-primary" disabled={busy}>{busy ? "Kaydediliyor…" : "Şifreyi değiştir"}</button>
      </form>
    </section>
  );
}

function DataExportCard({ api, token }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function download() {
    setError("");
    setBusy(true);
    try {
      const exported = await api.request("/auth/me/export", { token });
      const blob = new Blob([JSON.stringify(exported, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `careertracker-verilerim-${exported.exported_at.slice(0, 10)}.json`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (exportError) {
      if (exportError.status !== 401) setError("Veriler indirilemedi. Lütfen tekrar dene.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="account-card" aria-labelledby="data-export-title">
      <h2 id="data-export-title">Verilerimi indir</h2>
      <p className="muted">Başvuru, kişi, görev, aktivite, beceri ve e-posta önerisi kayıtlarının tamamı tek bir JSON dosyası olarak iner. Şifren dosyaya girmez.</p>
      {error && <p className="form-error" role="alert">{error}</p>}
      <button type="button" className="button" onClick={download} disabled={busy}>{busy ? "Hazırlanıyor…" : "Verilerimi indir"}</button>
    </section>
  );
}

function DeleteAccountForm({ api, token, onAccountDeleted }) {
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    setError("");
    if (!window.confirm("Hesabın ve tüm başvuru, kişi, görev ve aktivite kayıtların kalıcı olarak silinecek. Emin misin?")) return;
    setBusy(true);
    try {
      await api.request("/auth/me", { method: "DELETE", token, body: JSON.stringify({ password }) });
      onAccountDeleted();
    } catch (deleteError) {
      if (deleteError.status !== 401) setError(failureMessage(deleteError, "Hesap silme"));
      setBusy(false);
    }
  }

  return (
    <section className="account-card account-danger" aria-labelledby="delete-account-title">
      <h2 id="delete-account-title">Hesabı sil</h2>
      <p className="muted">Hesabın ve ona bağlı tüm kayıtlar kalıcı olarak silinir; bu işlem geri alınamaz.</p>
      <form className="account-form" onSubmit={submit}>
        <label htmlFor="delete-password">Onay için şifren</label>
        <input id="delete-password" type="password" autoComplete="current-password" required minLength={MIN_PASSWORD_LENGTH} value={password} onChange={(event) => setPassword(event.target.value)} />
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="button button-danger" disabled={busy}>{busy ? "Siliniyor…" : "Hesabımı kalıcı olarak sil"}</button>
      </form>
    </section>
  );
}

function AccountPanel({ api, token, email, onAccountDeleted }) {
  return (
    <div className="account-panel">
      {email && <p className="muted">Giriş yapılan hesap: <strong>{email}</strong></p>}
      <ChangePasswordForm api={api} token={token} />
      <DataExportCard api={api} token={token} />
      <DeleteAccountForm api={api} token={token} onAccountDeleted={onAccountDeleted} />
    </div>
  );
}

export default AccountPanel;

import { useState } from "react";
import { createApiClient } from "./api.js";

const resetApi = createApiClient();
const RESET_HASH = /^#sifre-sifirla=([\w-]{20,128})$/;

// E-postadaki bağlantı token'ı URL'nin # kısmında taşır (sunucuya gitmez).
export function readResetTokenFromUrl() {
  return RESET_HASH.exec(window.location.hash)?.[1] ?? null;
}

// Okunduktan sonra token adres çubuğundan ve tarayıcı geçmişinden silinir.
export function clearResetTokenFromUrl() {
  if (RESET_HASH.test(window.location.hash)) {
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
  }
}

function requestErrorMessage(error) {
  if (error.errorCode === "password_reset_unavailable") {
    return "Şifre sıfırlama şu anda kullanılamıyor. Lütfen daha sonra tekrar dene.";
  }
  if (error.status === 422) return "Geçerli bir e-posta adresi gir.";
  if (error.status === 429) return error.message;
  return "İstek gönderilemedi. Lütfen tekrar dene.";
}

export function ForgotPasswordForm({ initialEmail = "", onBack }) {
  const [email, setEmail] = useState(initialEmail);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await resetApi.request("/auth/password-reset/request", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      setSent(true);
    } catch (requestError) {
      setError(requestErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Şifreni sıfırla</h1>
      {sent ? (
        <p className="notice" role="status">
          Bu adrese kayıtlı bir hesap varsa sıfırlama bağlantısını gönderdik. Gelen kutunu ve spam
          klasörünü kontrol et; bağlantı 30 dakika geçerli.
        </p>
      ) : (
        <>
          <p className="muted">Hesabının e-posta adresini yaz; yeni şifre belirlemen için bir bağlantı gönderelim.</p>
          <form className="auth-form" onSubmit={submit}>
            <label htmlFor="reset-email">E-posta</label>
            <input id="reset-email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="button button-primary full-width" disabled={busy}>
              {busy ? "Gönderiliyor…" : "Sıfırlama bağlantısı gönder"}
            </button>
          </form>
        </>
      )}
      <p className="auth-switch">
        <button className="text-button" onClick={onBack}>Girişe dön</button>
      </p>
    </>
  );
}

export function ResetPasswordForm({ token, onDone, onRequestNewLink }) {
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [expired, setExpired] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (password !== repeat) {
      setError("Şifreler aynı değil.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await resetApi.request("/auth/password-reset/confirm", {
        method: "POST",
        body: JSON.stringify({ token, new_password: password }),
      });
      onDone();
    } catch (confirmError) {
      if (confirmError.errorCode === "reset_token_invalid") {
        setExpired(true);
      } else if (confirmError.status === 422) {
        setError("Şifre 8 ile 128 karakter arasında olmalı.");
      } else if (confirmError.status === 429) {
        setError(confirmError.message);
      } else {
        setError("Şifre güncellenemedi. Lütfen tekrar dene.");
      }
    } finally {
      setBusy(false);
    }
  }

  if (expired) {
    return (
      <>
        <h1>Bağlantının süresi dolmuş</h1>
        <p className="alert" role="alert">Bu bağlantı geçersiz, kullanılmış ya da süresi dolmuş.</p>
        <button className="button button-primary full-width" onClick={onRequestNewLink}>Yeni bağlantı iste</button>
      </>
    );
  }

  return (
    <>
      <h1>Yeni şifreni belirle</h1>
      <p className="muted">Şifre değişince açık olan tüm oturumların kapanır.</p>
      <form className="auth-form" onSubmit={submit}>
        <label htmlFor="new-password">Yeni şifre</label>
        <input id="new-password" type="password" autoComplete="new-password" minLength={8} maxLength={128} required aria-describedby="new-password-hint" value={password} onChange={(e) => setPassword(e.target.value)} />
        <small id="new-password-hint" className="muted">En az 8 karakter.</small>
        <label htmlFor="repeat-password">Yeni şifre (tekrar)</label>
        <input id="repeat-password" type="password" autoComplete="new-password" minLength={8} maxLength={128} required value={repeat} onChange={(e) => setRepeat(e.target.value)} />
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="button button-primary full-width" disabled={busy}>
          {busy ? "Kaydediliyor…" : "Şifreyi güncelle"}
        </button>
      </form>
    </>
  );
}

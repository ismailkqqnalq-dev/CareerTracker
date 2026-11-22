import { useEffect, useState } from "react";

// Hesap ayarlarında: kullanıcının işe alım e-postalarını yönlendireceği özel adres.
export default function EmailForwardingPanel({ api, token }) {
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    api.request("/email-insights/address", { token })
      .then((result) => { if (active) setState(result); })
      .catch((loadError) => { if (active && loadError.status !== 401) setError("Yönlendirme ayarı yüklenemedi."); });
    return () => { active = false; };
  }, [api, token]);

  async function run(action, message, confirmText) {
    if (confirmText && !window.confirm(confirmText)) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (action === "disable") {
        await api.request("/email-insights/address", { method: "DELETE", token });
        setState((current) => ({ ...current, enabled: false, address: null, verification_code: null }));
      } else {
        setState(await api.request("/email-insights/address", { method: "POST", token }));
      }
      setNotice(message);
    } catch (runError) {
      if (runError.status !== 401) setError("İşlem tamamlanamadı. Tekrar dene.");
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(state.address);
      setNotice("Adres kopyalandı.");
    } catch {
      setError("Kopyalanamadı; adresi elle seçip kopyalayabilirsin.");
    }
  }

  return (
    <section className="account-card" aria-labelledby="email-forwarding-title">
      <h2 id="email-forwarding-title">E-posta yönlendirme</h2>
      <p className="muted">
        Şirketlerden gelen e-postaları sana özel adrese yönlendirirsen, uygulama onları okuyup genel bakışta güncelleme önerir.
        Yalnızca başvurularından biriyle eşleşen e-postalar öneriye dönüşür; e-postaların metni saklanmaz.
      </p>
      {error && <p className="form-error" role="alert">{error}</p>}
      {notice && <p className="notice" role="status">{notice}</p>}
      {state && !state.enabled && (
        <button className="button button-primary" type="button" disabled={busy} onClick={() => run("rotate", "Yönlendirme adresin oluşturuldu.")}>Yönlendirme adresi oluştur</button>
      )}
      {state?.enabled && (
        <div className="forwarding-details">
          {state.address ? (
            <p className="forwarding-address"><code>{state.address}</code> <button className="button button-quiet" type="button" onClick={copy}>Kopyala</button></p>
          ) : (
            <p className="muted">Adresin hazır, ancak sunucuda e-posta alan adı henüz ayarlanmadı; uygulama yayına alınınca burada görünecek.</p>
          )}
          <ol className="forwarding-steps">
            <li>Gmail'de Ayarlar → Yönlendirme ve POP/IMAP → "Yönlendirme adresi ekle"ye bu adresi gir.</li>
            <li>Gmail bu adrese bir doğrulama kodu gönderir; kod birkaç dakika içinde aşağıda görünür.</li>
            <li>Ayarlar → Filtreler'de şirketlerden gelen e-postalar için (örneğin "kimden: trendyol.com") "Şuraya yönlendir" seç.</li>
          </ol>
          {state.verification_code
            ? <p className="forwarding-code">Gmail doğrulama kodu: <strong>{state.verification_code}</strong></p>
            : <p className="muted">Henüz bir Gmail doğrulama kodu gelmedi.</p>}
          <div className="detail-actions">
            <button className="button button-quiet" type="button" disabled={busy} onClick={() => run("rotate", "Yeni adres oluşturuldu; eski adrese gelen e-postalar artık işlenmeyecek.", "Adres değişirse eski adrese yönlendirilen e-postalar işlenmez. Devam edilsin mi?")}>Adresi yenile</button>
            <button className="button button-quiet" type="button" disabled={busy} onClick={() => run("disable", "E-posta yönlendirme kapatıldı.", "Yönlendirme kapatılsın mı? Bu adrese gelen e-postalar artık işlenmez.")}>Yönlendirmeyi kapat</button>
          </div>
        </div>
      )}
    </section>
  );
}

import { useEffect, useState } from "react";

const PERIODS = [3, 6, 12, 24, 60];

function ApplicationAnalyticsPanel({ api, token }) {
  const [months, setMonths] = useState(12);
  const [retryKey, setRetryKey] = useState(0);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let current = true;
    setLoading(true);
    setError("");
    setData(null);

    api.request(`/analytics/applications?months=${months}`, { token })
      .then((result) => {
        if (current) setData(result);
      })
      .catch((requestError) => {
        if (current && requestError.status !== 401) {
          setError("Başvuru analizi yüklenemedi. Bağlantını kontrol edip tekrar deneyebilirsin.");
        }
      })
      .finally(() => {
        if (current) setLoading(false);
      });

    return () => { current = false; };
  }, [api, token, months, retryKey]);

  const rows = Array.isArray(data?.applications_by_month) ? data.applications_by_month : [];
  const largestCount = Math.max(1, ...rows.map((row) => row.count));

  return (
    <section className="application-analytics-card" aria-labelledby="application-analytics-title">
      <div className="application-analytics-heading">
        <div>
          <h2 id="application-analytics-title">Aylık başvurular</h2>
          <p className="muted">Seçtiğin dönemde kaydettiğin başvuruların aylara göre sayısı.</p>
        </div>
        <label htmlFor="analytics-period">Dönem</label>
        <select
          id="analytics-period"
          value={months}
          onChange={(event) => setMonths(Number(event.target.value))}
          disabled={loading}
        >
          {PERIODS.map((period) => <option key={period} value={period}>{period} ay</option>)}
        </select>
      </div>

      {loading ? (
        <p className="application-analytics-state" role="status">Analiz yükleniyor…</p>
      ) : error ? (
        <div className="application-analytics-state" role="alert">
          <p>{error}</p>
          <button className="button button-primary" type="button" onClick={() => setRetryKey((value) => value + 1)}>
            Yeniden dene
          </button>
        </div>
      ) : (
        <>
          <p className="application-analytics-total"><strong>{data?.total_applications ?? 0}</strong> toplam başvuru</p>
          {rows.length ? (
            <ul className="application-month-list" aria-label="Aylık başvuru sayıları">
              {rows.map((row) => (
                <li key={row.month} aria-label={`${row.month}: ${row.count} başvuru`}>
                  <span className="application-month-label">{row.month}</span>
                  <span className="application-month-track" aria-hidden="true">
                    <span style={{ width: `${(row.count / largestCount) * 100}%` }} />
                  </span>
                  <strong>{row.count} başvuru</strong>
                </li>
              ))}
            </ul>
          ) : (
            <p className="application-analytics-state">Bu dönem için gösterilecek veri yok.</p>
          )}
          <p className="analysis-privacy">Aylık toplamlar yalnızca senin hesabındaki fırsatlardan hesaplanır.</p>
        </>
      )}
    </section>
  );
}

export default ApplicationAnalyticsPanel;

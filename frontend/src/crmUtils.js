// CRM ekranlarının ortak yardımcıları: başvuru listesi ve başvuru detay ekranı birlikte kullanır.

// Genel bakıştaki görüşme/teklif sayıları bu adlarla hesaplanır; serbest yazım sayıları bozabiliyordu.
export const OPPORTUNITY_STATUSES = ["Başvuruldu", "Ön görüşme", "Teknik mülakat", "Son mülakat", "Teklif", "Reddedildi"];

// Durum rozetinin rengi: süreçte, görüşmede, olumlu veya kapanmış.
const STATUS_TONES = {
  "Başvuruldu": "tone-applied",
  "Ön görüşme": "tone-interview",
  "Teknik mülakat": "tone-interview",
  "Son mülakat": "tone-interview",
  "Teklif": "tone-offer",
  "Reddedildi": "tone-closed",
};

export function statusTone(status) {
  return STATUS_TONES[status] ?? "tone-other";
}

export const today = () => {
  const date = new Date();
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
};

export function displayDate(value) {
  if (!value) return "Tarih yok";
  const parsed = new Date(`${String(value).slice(0, 10)}T12:00:00`);
  return Number.isNaN(parsed.valueOf()) ? String(value) : new Intl.DateTimeFormat("tr-TR", { dateStyle: "medium" }).format(parsed);
}

export function safeHttpUrl(value) {
  if (!value) return null;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

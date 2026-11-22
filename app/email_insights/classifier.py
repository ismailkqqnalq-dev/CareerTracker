"""İşe alım e-postası türü sınıflandırıcısı.

Asistanın Naive Bayes modeli (app.assistant.intent_model) yeniden kullanılır; buraya
özgü olan, e-postayı modele vermeden önceki temizliktir: başa yapıştırılmış başlıklar,
alıntılanmış eski mesajlar ve imzalar atılır, gövde makul bir uzunlukta kesilir.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

from app.assistant.intent_model import NaiveBayesIntentModel, Prediction

DATA_DIR = Path(__file__).resolve().parent
EMAIL_TYPES = ("basvuru_alindi", "mulakat_daveti", "degerlendirme", "teklif", "ret", "diger")
FALLBACK_TYPE = "diger"
# Yalnızca eğitim setinde leave-one-out ile seçildi; test seti seçime karışmadı.
# 0.99'da LOO doğruluğu korunurken yanlış durum önerileri 22'den 18'e iner.
# Bkz. scripts/evaluate_email_classifier.py.
CONFIDENCE_THRESHOLD = 0.99
MAX_BODY_CHARS = 2000
MAX_SIGNATURE_LINE_CHARS = 40

# E-posta istemcilerinin yanıt/iletme başlıkları: buradan sonrası eski mesajdır.
_QUOTE_START = re.compile(
    r"^(?:>|-{2,}\s*(?:original message|orijinal ileti|forwarded message|iletilen ileti)|"
    r"on .{4,120} wrote:|.{4,120} tarihinde .{0,120}yazdı:|from:|kimden:|gönderen:|sent:|gönderildi:)",
    re.IGNORECASE,
)
# Kısa bir kapanış satırı imzanın başladığını gösterir.
_SIGNATURE_START = re.compile(
    r"^(?:--\s*$|saygılarımızla|saygılarımla|iyi çalışmalar|sevgiler|best regards|kind regards|"
    r"regards|sincerely|cheers|thanks|thank you|teşekkürler)\b",
    re.IGNORECASE,
)
# Kullanıcı e-postayı başlıklarıyla birlikte yapıştırmış olabilir; baştaki başlıklar atlanır.
_LEADING_HEADER = re.compile(r"^(?:from|to|cc|date|subject|kimden|kime|bilgi|tarih|konu|gönderen|alıcı):", re.IGNORECASE)


def clean_email(subject: str | None, body: str | None) -> str:
    """Konu satırı ve gövdenin anlamlı kısmı; model ve eşleştirme bu metni görür."""
    kept: list[str] = []
    for raw_line in (body or "").splitlines():
        line = raw_line.strip()
        if not kept and (not line or _LEADING_HEADER.match(line)):
            continue
        if kept and _QUOTE_START.match(line):
            break
        if kept and len(line) <= MAX_SIGNATURE_LINE_CHARS and _SIGNATURE_START.match(line):
            break
        if line:
            kept.append(line)
    text = " ".join(kept)[:MAX_BODY_CHARS]
    return f"{(subject or '').strip()}\n{text}".strip()


def load_examples(file_name: str) -> tuple[list[str], list[str]]:
    data = json.loads((DATA_DIR / file_name).read_text(encoding="utf-8"))
    texts, labels = [], []
    for email_type, emails in data.items():
        for email in emails:
            texts.append(clean_email(email.get("subject"), email.get("body")))
            labels.append(email_type)
    return texts, labels


@lru_cache(maxsize=1)
def trained_model() -> NaiveBayesIntentModel:
    """Eğitim setinden bir kez, bellekte eğitilir; diske model dosyası yazılmaz."""
    return NaiveBayesIntentModel().fit(*load_examples("emails_train.json"))


def classify_text(text: str, model: NaiveBayesIntentModel | None = None) -> Prediction:
    prediction = (model or trained_model()).predict(text)
    if prediction.confidence < CONFIDENCE_THRESHOLD:
        return Prediction(intent=FALLBACK_TYPE, confidence=prediction.confidence)
    return prediction


def classify_email(subject: str | None, body: str | None) -> Prediction:
    return classify_text(clean_email(subject, body))

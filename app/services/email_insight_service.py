"""Gelen bir işe alım e-postasını anlamlandırır ve başvuru için güncelleme önerir.

Hiçbir şey kaydedilmez ve hiçbir başvuru kendiliğinden değişmez: sonuç, kullanıcının
tek tıkla uygulayabileceği bir öneridir. E-posta metni saklanmaz.
"""

import re
from datetime import date, datetime, timedelta

from app.assistant.intent_model import fold_text
from app.email_insights.classifier import FALLBACK_TYPE, classify_text, clean_email
from app.models.opportunity import Opportunity
from app.services.assistant_service import _company_key

ASSESSMENT_DUE_DAYS = 3
MAX_CANDIDATES = 5
# Bu alan adları şirketi değil, işe alım platformunu veya kişisel e-posta servisini gösterir.
_PLATFORM_DOMAINS = {
    "gmail", "googlemail", "outlook", "hotmail", "live", "yahoo", "icloud", "yandex", "proton", "protonmail",
    "greenhouse", "lever", "myworkdayjobs", "workday", "smartrecruiters", "workable", "teamtailor",
    "bamboohr", "recruitee", "personio", "ashbyhq", "jobvite", "icims", "successfactors", "taleo",
    "kariyer", "linkedin", "indeed", "secretcv", "yenibiris", "peoplise", "hrpeak", "hackerrank", "codility",
    "mail", "email", "noreply", "no-reply",
}
_EMAIL_ADDRESS = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")
_SECOND_LEVEL = {"com", "net", "org", "gov", "edu", "co", "gen", "bel", "web", "biz", "info"}

TYPE_LABELS = {
    "basvuru_alindi": "başvurunun alındığını bildiren bir e-posta",
    "mulakat_daveti": "bir mülakat daveti",
    "degerlendirme": "bir test veya ödev daveti",
    "teklif": "bir iş teklifi",
    "ret": "olumsuz bir dönüş",
    "diger": "işe alımla ilgili görünmeyen bir e-posta",
}
_NEXT_INTERVIEW_STAGE = {
    "basvuruldu": "Ön görüşme",
    "on gorusme": "Teknik mülakat",
    "teknik mulakat": "Son mülakat",
}


def sender_company_label(sender: str | None) -> str | None:
    """'Trendyol İK <ik@careers.trendyol.com>' → 'trendyol'; platform alan adlarında None."""
    match = _EMAIL_ADDRESS.search(sender or "")
    if not match:
        return None
    labels = match.group(1).lower().split(".")
    # Ülke uzantılı ikinci düzey alan adlarını at: garanti.com.tr → garanti.
    while len(labels) > 1 and (labels[-1] in _SECOND_LEVEL or len(labels[-1]) == 2):
        labels.pop()
    if not labels:
        return None
    label = fold_text(labels[-1]).replace(" ", "")
    return None if label in _PLATFORM_DOMAINS or len(label) < 3 else label


def match_opportunities(db, user_id: int, sender: str | None, text: str) -> list[Opportunity]:
    """Gönderen alan adı veya metinde geçen şirket adıyla eşleşen başvurular, en yeni önce."""
    domain_label = sender_company_label(sender)
    display_name = (sender or "").split("<", 1)[0]
    words = fold_text(f"{display_name} {text}").split()
    matches = []
    for opportunity in db.query(Opportunity).filter(Opportunity.user_id == user_id).all():
        key = _company_key(opportunity.company)
        if not key:
            continue
        by_domain = bool(domain_label) and (domain_label.startswith(key) or key.startswith(domain_label))
        # Türkçe ekler kelime sonuna gelir: "trendyol'daki" → "trendyol daki" kelimesi "trendyol" ile başlar.
        by_text = any(word.startswith(key) for word in words)
        if by_domain or by_text:
            matches.append(opportunity)
    return sorted(matches, key=lambda item: item.id, reverse=True)


def suggest_update(email_type: str, opportunity: Opportunity, today: date) -> dict:
    """E-posta türüne göre önerilen değişiklikler; mevcut değerle aynı olanlar önerilmez."""
    suggestion = {"status": None, "last_contact_date": None, "task": None}
    if email_type == FALLBACK_TYPE:
        return suggestion

    last_contact = opportunity.last_contact_date
    if isinstance(last_contact, datetime):
        last_contact = last_contact.date()
    if last_contact != today:
        suggestion["last_contact_date"] = today

    current_key = fold_text(opportunity.status or "")
    if email_type == "ret":
        target = "Reddedildi"
    elif email_type == "teklif":
        target = "Teklif"
    elif email_type == "mulakat_daveti":
        # Davet bir sonraki görüşme aşamasını gösterir; son mülakattan sonrası tahmin edilmez.
        target = _NEXT_INTERVIEW_STAGE.get(current_key)
        if target is None and current_key not in {"son mulakat", "teklif", "reddedildi"}:
            target = "Ön görüşme"
    else:
        target = None
    if target and fold_text(target) != current_key:
        suggestion["status"] = target

    if email_type == "degerlendirme":
        suggestion["task"] = {
            "description": f"{opportunity.company or 'Başvuru'} değerlendirmesini (test/ödev) tamamla",
            "due_date": today + timedelta(days=ASSESSMENT_DUE_DAYS),
        }
    return suggestion


def _summary(opportunity: Opportunity) -> dict:
    return {
        "id": opportunity.id,
        "company": opportunity.company,
        "position": opportunity.position,
        "status": opportunity.status,
    }


def analyze(db, user_id: int, *, subject: str, body: str, sender: str, opportunity_id: int | None, today: date) -> dict:
    """Sonuç: tür, güven, eşleşen başvuru (veya adaylar) ve öneri. Bilinmeyen başvuru için None döner."""
    text = clean_email(subject, body)
    prediction = classify_text(text)
    email_type = prediction.intent

    if opportunity_id is not None:
        opportunity = (
            db.query(Opportunity)
            .filter(Opportunity.id == opportunity_id, Opportunity.user_id == user_id)
            .first()
        )
        if opportunity is None:
            return None
        candidates = [opportunity]
    else:
        candidates = match_opportunities(db, user_id, sender, text)

    result = {
        "type": email_type,
        "confidence": round(prediction.confidence, 4),
        "opportunity": None,
        "candidates": [],
        "suggestion": {"status": None, "last_contact_date": None, "task": None},
        "explanation": "",
    }
    label = TYPE_LABELS[email_type]
    if email_type == FALLBACK_TYPE:
        result["explanation"] = f"Bu {label}; başvuru için bir değişiklik önerilmiyor."
        return result
    if len(candidates) == 1:
        opportunity = candidates[0]
        result["opportunity"] = _summary(opportunity)
        result["suggestion"] = suggest_update(email_type, opportunity, today)
        result["explanation"] = f"Bu, {opportunity.company} başvurusu için {label} gibi görünüyor."
    elif candidates:
        result["candidates"] = [_summary(item) for item in candidates[:MAX_CANDIDATES]]
        result["explanation"] = f"Bu {label} gibi görünüyor, ama birden fazla başvuruyla eşleşiyor; hangisi olduğunu seç."
    else:
        result["explanation"] = f"Bu {label} gibi görünüyor, ama hiçbir başvurunla eşleştiremedim."
    return result

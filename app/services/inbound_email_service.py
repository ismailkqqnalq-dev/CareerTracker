"""Yönlendirme adresleri, gelen e-postaların işlenmesi ve bekleyen öneriler.

Akış: kullanıcı işe alım e-postalarını kendisine özel adrese yönlendirir; gelen
e-posta servisi her e-postayı POST /inbound/email ile iletir. E-posta sınıflandırılır,
kullanıcının bir başvurusuyla tek başına eşleşirse bekleyen öneri olarak kaydedilir.
E-postanın metni hiçbir zaman saklanmaz.
"""

import hmac
import os
import re
import secrets
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.email_insights.classifier import FALLBACK_TYPE
from app.models.email_insights import EmailSuggestion, InboundAddress
from app.models.opportunity import Opportunity
from app.models.tasks import Task
from app.services import email_insight_service

SUBJECT_LIMIT = 500
SENDER_LIMIT = 320
_ADDRESS = re.compile(r"([\w.+-]+)@([\w-]+(?:\.[\w-]+)+)")
# Gmail yönlendirme onayı: "Confirmation code: 123456789" / "Onay kodu: 123456789".
_GMAIL_CODE = re.compile(r"(?:confirmation code|onay kodu|doğrulama kodu)\D{0,10}(\d{6,12})", re.IGNORECASE)


class SuggestionNotFound(LookupError):
    pass


class SuggestionNotPending(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def inbound_domain() -> str | None:
    value = os.getenv("INBOUND_EMAIL_DOMAIN", "").strip().lower()
    return value or None


def inbound_secret() -> str | None:
    value = os.getenv("INBOUND_EMAIL_SECRET", "").strip()
    return value or None


def secret_matches(provided: str | None) -> bool:
    expected = inbound_secret()
    # Sabit süreli karşılaştırma: anahtar, yanıt süresinden harf harf tahmin edilemez.
    return bool(expected and provided) and hmac.compare_digest(provided.encode(), expected.encode())


def get_address(db: Session, user_id: int) -> InboundAddress | None:
    return db.query(InboundAddress).filter(InboundAddress.user_id == user_id).first()


def rotate_address(db: Session, user_id: int) -> InboundAddress:
    """Adres yoksa oluşturur, varsa yenisiyle değiştirir; eski adrese gelenler artık işlenmez."""
    address = get_address(db, user_id)
    if address is None:
        address = InboundAddress(user_id=user_id)
        db.add(address)
    # 80 bit rastgelelik: tahmin edilerek başkasının adresine e-posta düşürülemez.
    address.local_part = secrets.token_hex(10)
    address.verification_code = None
    address.verification_received_at = None
    db.commit()
    db.refresh(address)
    return address


def disable_address(db: Session, user_id: int) -> None:
    db.query(InboundAddress).filter(InboundAddress.user_id == user_id).delete(synchronize_session=False)
    db.commit()


def _local_part(recipient: str) -> str | None:
    match = _ADDRESS.search(recipient or "")
    return match.group(1).lower() if match else None


def _is_gmail_verification(sender: str, subject: str) -> bool:
    folded = f"{sender} {subject}".lower()
    return "forwarding-noreply@google.com" in folded or "gmail forwarding confirmation" in folded


def handle_inbound(db: Session, *, recipient: str, sender: str, subject: str, text: str, today: date) -> str:
    """Sonuç: 'ignored', 'verification' veya 'suggested'. Çağırana ayrım gösterilmez."""
    local_part = _local_part(recipient)
    address = (
        db.query(InboundAddress).filter(InboundAddress.local_part == local_part).first()
        if local_part else None
    )
    if address is None:
        return "ignored"

    if _is_gmail_verification(sender, subject):
        code = _GMAIL_CODE.search(f"{subject}\n{text}")
        if code:
            address.verification_code = code.group(1)
            address.verification_received_at = _now()
            db.commit()
            return "verification"
        return "ignored"

    analysis = email_insight_service.analyze(
        db,
        address.user_id,
        subject=subject,
        body=text,
        sender=sender,
        opportunity_id=None,
        today=today,
    )
    suggestion = analysis["suggestion"]
    if analysis["type"] == FALLBACK_TYPE or analysis["opportunity"] is None or not any(suggestion.values()):
        # Eşleşmeyen veya öneri doğurmayan e-postadan hiçbir iz saklanmaz.
        return "ignored"

    opportunity_id = analysis["opportunity"]["id"]
    duplicate = db.query(EmailSuggestion).filter(
        EmailSuggestion.user_id == address.user_id,
        EmailSuggestion.opportunity_id == opportunity_id,
        EmailSuggestion.email_type == analysis["type"],
        EmailSuggestion.subject == subject[:SUBJECT_LIMIT],
        EmailSuggestion.state == "pending",
    ).first()
    if duplicate:
        return "suggested"

    task = suggestion["task"] or {}
    db.add(EmailSuggestion(
        user_id=address.user_id,
        opportunity_id=opportunity_id,
        email_type=analysis["type"],
        confidence=analysis["confidence"],
        sender=sender[:SENDER_LIMIT],
        subject=subject[:SUBJECT_LIMIT],
        received_at=_now(),
        suggested_status=suggestion["status"],
        suggested_last_contact_date=suggestion["last_contact_date"],
        suggested_task_description=task.get("description"),
        suggested_task_due_date=task.get("due_date"),
        state="pending",
    ))
    db.commit()
    return "suggested"


def list_suggestions(db: Session, user_id: int, state: str = "pending") -> list[tuple[EmailSuggestion, Opportunity]]:
    return (
        db.query(EmailSuggestion, Opportunity)
        .join(Opportunity, Opportunity.id == EmailSuggestion.opportunity_id)
        .filter(
            EmailSuggestion.user_id == user_id,
            Opportunity.user_id == user_id,
            EmailSuggestion.state == state,
        )
        .order_by(EmailSuggestion.received_at.desc(), EmailSuggestion.id.desc())
        .limit(50)
        .all()
    )


def _owned_pending(db: Session, user_id: int, suggestion_id: int) -> tuple[EmailSuggestion, Opportunity]:
    row = (
        db.query(EmailSuggestion, Opportunity)
        .join(Opportunity, Opportunity.id == EmailSuggestion.opportunity_id)
        .filter(
            EmailSuggestion.id == suggestion_id,
            EmailSuggestion.user_id == user_id,
            Opportunity.user_id == user_id,
        )
        .first()
    )
    if row is None:
        raise SuggestionNotFound
    if row[0].state != "pending":
        raise SuggestionNotPending
    return row


def apply_suggestion(db: Session, user_id: int, suggestion_id: int) -> tuple[EmailSuggestion, Opportunity]:
    """Önerilen durum, son temas ve görevi tek işlemde uygular."""
    suggestion, opportunity = _owned_pending(db, user_id, suggestion_id)
    if suggestion.suggested_status:
        opportunity.status = suggestion.suggested_status
    if suggestion.suggested_last_contact_date:
        opportunity.last_contact_date = suggestion.suggested_last_contact_date
    if suggestion.suggested_task_description:
        db.add(Task(
            user_id=user_id,
            opportunity_id=opportunity.id,
            description=suggestion.suggested_task_description,
            due_date=suggestion.suggested_task_due_date,
            is_completed=False,
        ))
    suggestion.state = "applied"
    suggestion.resolved_at = _now()
    db.commit()
    return suggestion, opportunity


def dismiss_suggestion(db: Session, user_id: int, suggestion_id: int) -> tuple[EmailSuggestion, Opportunity]:
    suggestion, opportunity = _owned_pending(db, user_id, suggestion_id)
    suggestion.state = "dismissed"
    suggestion.resolved_at = _now()
    db.commit()
    return suggestion, opportunity


def latest_email_event(db: Session, user_id: int, opportunity_id: int) -> EmailSuggestion | None:
    """Asistanın cevabında gösterilmek üzere bu başvuru için gelen son e-posta."""
    return (
        db.query(EmailSuggestion)
        .filter(EmailSuggestion.user_id == user_id, EmailSuggestion.opportunity_id == opportunity_id)
        .order_by(EmailSuggestion.received_at.desc(), EmailSuggestion.id.desc())
        .first()
    )

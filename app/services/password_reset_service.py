"""Şifremi unuttum: tek kullanımlık, kısa ömürlü sıfırlama bağlantıları.

Ham token yalnızca e-postadaki bağlantıda bulunur; veritabanında SHA-256 özeti tutulur.
Yeni bir istek, kullanıcının önceki kullanılmamış bağlantılarını geçersiz kılar.
Şifre değişince kullanıcının tüm oturumları kapanır.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.password_reset_tokens import PasswordResetToken
from app.models.users import User
from app.security import hash_password
from app.services import mailer, session_service

TOKEN_LIFETIME = timedelta(minutes=30)
# Kullanılmış veya süresi dolmuş kayıtlar bu süre sonra silinir.
RETENTION = timedelta(days=1)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    # SQLite saat dilimi bilgisini korumaz; kayıtlar her zaman UTC yazılır.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _find_active_user(db: Session, email: str) -> User | None:
    normalized_email = email.strip().lower()
    user = db.query(User).filter(func.lower(User.email) == normalized_email).first()
    return user if user is not None and user.is_active else None


def create_reset_token(db: Session, email: str) -> tuple[User, str] | None:
    """Kayıtlı ve etkin bir hesap için yeni bağlantı üretir; yoksa None döner."""
    user = _find_active_user(db, email)
    if user is None:
        return None

    now = _now()
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        or_(
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.created_at < now - RETENTION,
        ),
    ).delete(synchronize_session=False)
    raw_token = secrets.token_urlsafe(32)
    db.add(PasswordResetToken(
        user_id=user.id,
        token_hash=_hash(raw_token),
        created_at=now,
        expires_at=now + TOKEN_LIFETIME,
    ))
    db.commit()
    return user, raw_token


def reset_link(raw_token: str) -> str:
    # Token URL'nin # kısmında: tarayıcı bunu sunucuya ve Referer başlığına göndermez.
    return f"{mailer.get_mail_settings().public_app_url}/#sifre-sifirla={raw_token}"


def send_reset_email(email: str, raw_token: str) -> None:
    minutes = int(TOKEN_LIFETIME.total_seconds() // 60)
    body = (
        "Merhaba,\n\n"
        "CareerTracker hesabın için şifre sıfırlama isteği aldık. Yeni şifreni belirlemek için "
        f"aşağıdaki bağlantıyı aç (bağlantı {minutes} dakika geçerli ve tek kullanımlık):\n\n"
        f"{reset_link(raw_token)}\n\n"
        "Bu isteği sen yapmadıysan bu e-postayı yok sayabilirsin; şifren değişmez.\n"
    )
    mailer.send_email(email, "CareerTracker şifre sıfırlama", body)


def reset_password(db: Session, raw_token: str, new_password: str) -> bool:
    """Geçerli bir bağlantıyla şifreyi değiştirir ve tüm oturumları kapatır."""
    now = _now()
    record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == _hash(raw_token),
    ).first()
    if record is None or record.used_at is not None or _aware(record.expires_at) <= now:
        return False

    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        return False

    # Aynı bağlantı aynı anda iki kez gönderilirse yalnızca biri kazanır.
    claimed = db.query(PasswordResetToken).filter(
        PasswordResetToken.id == record.id,
        PasswordResetToken.used_at.is_(None),
    ).update({PasswordResetToken.used_at: now}, synchronize_session=False)
    if claimed != 1:
        db.rollback()
        return False

    user.hashed_password = hash_password(new_password)
    db.commit()
    session_service.revoke_all_for_user(db, user.id)
    return True

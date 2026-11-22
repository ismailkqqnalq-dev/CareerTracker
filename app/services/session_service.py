"""Yenileme token'ları: verme, rotasyon, yeniden kullanım tespiti ve iptal.

Ham token yalnızca istemciye (httpOnly çereze) gider; veritabanında SHA-256
özeti tutulur. Her yenilemede eski token iptal edilip aynı aileden yenisi verilir.
İptal edilmiş bir token tekrar gelirse bu çalınma belirtisidir ve aile iptal edilir;
iki sekmenin aynı anda yenilemesi bu kuralı kısa bir tolerans süresiyle aşar.
"""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.refresh_tokens import RefreshToken
from app.models.users import User

PERSISTENT_LIFETIME = timedelta(days=30)
SESSION_LIFETIME = timedelta(days=1)
ROTATION_GRACE = timedelta(seconds=30)
# İptal edilmiş/süresi dolmuş kayıtlar bu süre sonra temizlenir; tolerans süresinden uzun olmalı.
RETENTION = timedelta(days=1)


class SessionError(Exception):
    def __init__(self, error_code: str):
        super().__init__(error_code)
        self.error_code = error_code


@dataclass(frozen=True)
class IssuedSession:
    user: User
    refresh_token: str
    persistent: bool


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    # SQLite saat dilimi bilgisini korumaz; kayıtlar her zaman UTC yazılır.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _purge_stale(db: Session, user_id: int, now: datetime) -> None:
    cutoff = now - RETENTION
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        or_(RefreshToken.expires_at < cutoff, RefreshToken.revoked_at < cutoff),
    ).delete(synchronize_session=False)


def _add_token(db: Session, user_id: int, persistent: bool, family_id: str, now: datetime) -> str:
    raw_token = secrets.token_urlsafe(32)
    db.add(RefreshToken(
        user_id=user_id,
        token_hash=_hash(raw_token),
        family_id=family_id,
        persistent=persistent,
        created_at=now,
        expires_at=now + (PERSISTENT_LIFETIME if persistent else SESSION_LIFETIME),
    ))
    return raw_token


def issue(db: Session, user: User, persistent: bool) -> str:
    """Yeni bir giriş için yeni bir token ailesi başlatır."""
    now = _now()
    _purge_stale(db, user.id, now)
    raw_token = _add_token(db, user.id, persistent, str(uuid.uuid4()), now)
    db.commit()
    return raw_token


def rotate(db: Session, raw_token: str | None) -> IssuedSession:
    if not raw_token:
        raise SessionError("refresh_token_missing")
    record = db.query(RefreshToken).filter(RefreshToken.token_hash == _hash(raw_token)).first()
    if record is None:
        raise SessionError("refresh_token_invalid")

    now = _now()
    if record.revoked_at is not None:
        if now - _aware(record.revoked_at) <= ROTATION_GRACE:
            # Büyük olasılıkla başka bir sekme az önce yeniledi; aile korunur.
            raise SessionError("refresh_token_rotated")
        revoke_family(db, record.family_id)
        raise SessionError("refresh_token_reused")
    if _aware(record.expires_at) <= now:
        raise SessionError("refresh_token_expired")

    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        raise SessionError("refresh_token_invalid")

    if not claim(db, record.id, now):
        # Aynı token'la eş zamanlı gelen başka bir istek rotasyonu kazandı.
        db.rollback()
        raise SessionError("refresh_token_rotated")
    new_token = _add_token(db, user.id, record.persistent, record.family_id, now)
    db.commit()
    return IssuedSession(user=user, refresh_token=new_token, persistent=record.persistent)


def claim(db: Session, record_id: int, now: datetime) -> bool:
    """Token'ı yalnızca hâlâ iptal edilmemişse iptal eder; tek bir istek kazanır.

    Önce okuyup sonra yazmak yarış durumuna açıktır: eş zamanlı iki istek token'ı
    geçerli görüp ikisi de yeni token alırdı. Koşullu UPDATE atomiktir.
    """
    updated = db.query(RefreshToken).filter(
        RefreshToken.id == record_id,
        RefreshToken.revoked_at.is_(None),
    ).update({RefreshToken.revoked_at: now}, synchronize_session=False)
    return updated == 1


def revoke(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    db.query(RefreshToken).filter(
        RefreshToken.token_hash == _hash(raw_token),
        RefreshToken.revoked_at.is_(None),
    ).update({RefreshToken.revoked_at: _now()}, synchronize_session=False)
    db.commit()


def revoke_family(db: Session, family_id: str) -> None:
    db.query(RefreshToken).filter(
        RefreshToken.family_id == family_id,
        RefreshToken.revoked_at.is_(None),
    ).update({RefreshToken.revoked_at: _now()}, synchronize_session=False)
    db.commit()


def revoke_all_for_user(db: Session, user_id: int) -> None:
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked_at.is_(None),
    ).update({RefreshToken.revoked_at: _now()}, synchronize_session=False)
    db.commit()


def is_persistent(db: Session, user_id: int, raw_token: str | None) -> bool:
    """Mevcut çerezin 'beni hatırla' ile mi açıldığı; bilinmiyorsa False."""
    if not raw_token:
        return False
    record = db.query(RefreshToken).filter(
        RefreshToken.token_hash == _hash(raw_token),
        RefreshToken.user_id == user_id,
    ).first()
    return bool(record and record.persistent)

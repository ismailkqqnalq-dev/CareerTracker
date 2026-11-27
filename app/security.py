from datetime import datetime, timedelta, timezone
import os
import threading

import jwt
from dotenv import load_dotenv
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

load_dotenv()

password_hash = PasswordHash.recommended()
# Argon2 (varsayılan ayar) her hash için ~64 MB bellek ayırır. Sınır olmazsa eşzamanlı
# kayıt/giriş istekleri sunucu iş parçacığı sayısı kadar hash'i aynı anda çalıştırıp
# küçük bir sunucunun belleğini tüketebilir. Hash zaten CPU'ya bağlı; sınır hızı düşürmez.
MAX_CONCURRENT_PASSWORD_HASHES = 4
_password_hash_slots = threading.BoundedSemaphore(MAX_CONCURRENT_PASSWORD_HASHES)
DUMMY_PASSWORD_HASH = password_hash.hash("careertracker-dummy-password")

ALGORITHM = "HS256"
# Kısa ömürlü erişim token'ı; oturum httpOnly yenileme çereziyle sürer.
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_COOKIE_NAME = "careertracker_refresh"
# Çerezle çalışan uç noktalar bu başlığı ister: başka bir site, CORS izni
# olmadan özel başlık gönderemez (SameSite=Strict'e ek CSRF katmanı).
CSRF_HEADER_NAME = "X-Requested-With"
CSRF_HEADER_VALUE = "CareerTracker"
MIN_JWT_SECRET_BYTES = 32
_PLACEHOLDER_SECRET_VALUES = frozenset(
    {
        "replace-with-a-random-secret",
        "development-placeholder-secret-key",
        "your-secret-key",
        "change-me",
        "changeme",
        "change-this-secret",
    }
)


def validate_jwt_secret_key() -> str:
    secret_key = os.getenv("JWT_SECRET_KEY", "").strip()
    if (
        len(secret_key.encode("utf-8")) < MIN_JWT_SECRET_BYTES
        or secret_key.casefold() in _PLACEHOLDER_SECRET_VALUES
    ):
        raise RuntimeError(
            "JWT_SECRET_KEY must be a non-placeholder value of at least 32 bytes."
        )
    return secret_key


def registration_is_enabled() -> bool:
    configured = os.getenv("REGISTRATION_ENABLED")
    if configured is None:
        app_env = os.getenv("APP_ENV", "").strip().casefold()
        return app_env == "development"

    value = configured.strip().casefold()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError("REGISTRATION_ENABLED must be a boolean value.")


def refresh_cookie_is_secure() -> bool:
    """Varsayılan: geliştirme dışında yalnızca HTTPS; COOKIE_SECURE açıkça ezebilir."""
    configured = os.getenv("COOKIE_SECURE")
    if configured is None:
        return os.getenv("APP_ENV", "").strip().casefold() != "development"

    value = configured.strip().casefold()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError("COOKIE_SECURE must be a boolean value.")


def validate_security_configuration() -> None:
    validate_jwt_secret_key()
    registration_is_enabled()
    refresh_cookie_is_secure()


def hash_password(password: str) -> str:
    with _password_hash_slots:
        return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    with _password_hash_slots:
        return password_hash.verify(password, hashed_password)


def create_access_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, validate_jwt_secret_key(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(
            token,
            validate_jwt_secret_key(),
            algorithms=[ALGORITHM],
        )
    except InvalidTokenError:
        return None

    subject = payload.get("sub")
    return subject if isinstance(subject, str) else None

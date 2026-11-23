"""Giden e-posta: SMTP ile gönderir; geliştirmede yalnızca sunucu günlüğüne yazar.

Hangi servis kullanılırsa kullanılsın (Brevo, Resend, Gmail...) SMTP ayarları yeterlidir:

    EMAIL_BACKEND=smtp
    SMTP_HOST=smtp.example.com
    SMTP_PORT=587                # 465 ise SMTP_SECURITY=ssl
    SMTP_USERNAME=...
    SMTP_PASSWORD=...
    SMTP_FROM="CareerTracker <bildirim@example.com>"
    PUBLIC_APP_URL=https://careertracker.example.com
"""

from dataclasses import dataclass
from email.message import EmailMessage
import logging
import os
import smtplib
import ssl

logger = logging.getLogger(__name__)

BACKENDS = ("console", "smtp", "disabled")
DEVELOPMENT_APP_URL = "http://localhost:5173"
SMTP_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class MailSettings:
    backend: str
    public_app_url: str
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_security: str = "starttls"


def _is_development() -> bool:
    return os.getenv("APP_ENV", "").strip().casefold() == "development"


def get_mail_settings() -> MailSettings:
    """Ortam değişkenlerini okur; eksik veya tutarsız ayarda hata verir."""
    development = _is_development()
    backend = os.getenv("EMAIL_BACKEND", "").strip().casefold() or (
        "console" if development else "disabled"
    )
    if backend not in BACKENDS:
        raise RuntimeError("EMAIL_BACKEND must be one of: console, smtp, disabled.")
    if backend == "console" and not development:
        # Sıfırlama bağlantıları günlüğe düşerse günlüğü okuyan herkes hesaba girebilir.
        raise RuntimeError("EMAIL_BACKEND=console is only allowed when APP_ENV=development.")

    public_app_url = os.getenv("PUBLIC_APP_URL", "").strip().rstrip("/")
    if not public_app_url and development:
        public_app_url = DEVELOPMENT_APP_URL
    if backend != "disabled" and not public_app_url.startswith(("https://", "http://")):
        raise RuntimeError("PUBLIC_APP_URL must be set to the site address (https://...).")

    if backend != "smtp":
        return MailSettings(backend=backend, public_app_url=public_app_url)

    security = os.getenv("SMTP_SECURITY", "starttls").strip().casefold()
    if security not in ("starttls", "ssl"):
        raise RuntimeError("SMTP_SECURITY must be starttls or ssl.")
    try:
        port = int(os.getenv("SMTP_PORT", "465" if security == "ssl" else "587"))
    except ValueError as error:
        raise RuntimeError("SMTP_PORT must be a port number.") from error
    settings = MailSettings(
        backend=backend,
        public_app_url=public_app_url,
        smtp_host=os.getenv("SMTP_HOST", "").strip(),
        smtp_port=port,
        smtp_username=os.getenv("SMTP_USERNAME", "").strip(),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        smtp_from=os.getenv("SMTP_FROM", "").strip(),
        smtp_security=security,
    )
    if not settings.smtp_host or not settings.smtp_from:
        raise RuntimeError("EMAIL_BACKEND=smtp needs SMTP_HOST and SMTP_FROM.")
    return settings


def validate_mail_configuration() -> None:
    get_mail_settings()


def email_is_enabled() -> bool:
    return get_mail_settings().backend != "disabled"


def _send_smtp(settings: MailSettings, message: EmailMessage) -> None:
    context = ssl.create_default_context()
    if settings.smtp_security == "ssl":
        server = smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS, context=context
        )
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS)
    with server:
        if settings.smtp_security == "starttls":
            server.starttls(context=context)
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)


def send_email(to: str, subject: str, body: str) -> bool:
    """E-postayı gönderir; hata isteği bozmaz, günlüğe yazılır (alıcı adresi yazılmaz)."""
    settings = get_mail_settings()
    if settings.backend == "disabled":
        return False

    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    message["From"] = settings.smtp_from or "CareerTracker <no-reply@localhost>"
    message.set_content(body)

    if settings.backend == "console":
        logger.warning("Geliştirme e-postası (gönderilmedi)\nKonu: %s\n\n%s", subject, body)
        return True

    try:
        _send_smtp(settings, message)
    except (OSError, smtplib.SMTPException) as error:
        logger.error("E-posta gönderilemedi: %s", type(error).__name__)
        return False
    return True

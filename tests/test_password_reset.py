from datetime import datetime, timedelta, timezone
import re

import pytest

from app.models.password_reset_tokens import PasswordResetToken
from app.services import mailer

EMAIL = "owner@example.com"
OLD_PASSWORD = "StrongPass123"
NEW_PASSWORD = "BrandNewPass456"
CSRF = {"X-Requested-With": "CareerTracker"}


@pytest.fixture()
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, "send_email", lambda to, subject, body: sent.append((to, subject, body)) or True)
    return sent


def _register(client, email=EMAIL):
    assert client.post("/auth/register", json={"email": email, "password": OLD_PASSWORD}).status_code == 201


def _login(client, password, email=EMAIL):
    return client.post("/auth/token", data={"username": email, "password": password, "remember_me": "true"})


def _request(client, email=EMAIL):
    return client.post("/auth/password-reset/request", json={"email": email})


def _token_from(body):
    return re.search(r"#sifre-sifirla=([\w-]+)", body).group(1)


def _confirm(client, token, password=NEW_PASSWORD):
    return client.post("/auth/password-reset/confirm", json={"token": token, "new_password": password})


def test_reset_link_lets_the_user_choose_a_new_password(client, outbox):
    _register(client)

    assert _request(client, " Owner@Example.com ").status_code == 202

    [(to, subject, body)] = outbox
    assert to == EMAIL
    assert "şifre" in subject.lower()
    assert body.count("http://localhost:5173/#sifre-sifirla=") == 1
    assert _confirm(client, _token_from(body)).status_code == 204
    assert _login(client, OLD_PASSWORD).status_code == 401
    assert _login(client, NEW_PASSWORD).status_code == 200


def test_unknown_email_gets_the_same_answer_and_no_email(client, outbox):
    _register(client)

    known = _request(client)
    unknown = _request(client, "nobody@example.com")

    assert (unknown.status_code, unknown.json()) == (known.status_code, known.json())
    assert [to for to, _, _ in outbox] == [EMAIL]


def test_link_works_only_once(client, outbox):
    _register(client)
    _request(client)
    token = _token_from(outbox[0][2])

    assert _confirm(client, token).status_code == 204
    second = _confirm(client, token, "AnotherPass789")

    assert second.status_code == 400
    assert second.json()["error_code"] == "reset_token_invalid"
    assert _login(client, NEW_PASSWORD).status_code == 200


def test_a_new_request_cancels_the_previous_link(client, outbox):
    _register(client)
    _request(client)
    _request(client)
    first, second = (_token_from(body) for _, _, body in outbox)

    assert _confirm(client, first).status_code == 400
    assert _confirm(client, second).status_code == 204


def test_expired_link_is_rejected(client, outbox, db_session):
    _register(client)
    _request(client)
    token = _token_from(outbox[0][2])
    db_session.query(PasswordResetToken).update(
        {PasswordResetToken.expires_at: datetime.now(timezone.utc) - timedelta(seconds=1)}
    )
    db_session.commit()

    assert _confirm(client, token).status_code == 400
    assert _login(client, OLD_PASSWORD).status_code == 200


def test_only_a_hash_of_the_token_is_stored(client, outbox, db_session):
    _register(client)
    _request(client)
    token = _token_from(outbox[0][2])

    [record] = db_session.query(PasswordResetToken).all()
    assert token not in record.token_hash
    assert len(record.token_hash) == 64


def test_reset_signs_out_every_existing_session(client, outbox):
    _register(client)
    assert _login(client, OLD_PASSWORD).status_code == 200
    assert client.post("/auth/refresh", headers=CSRF).status_code == 200
    _request(client)

    response = _confirm(client, _token_from(outbox[0][2]))

    assert response.status_code == 204
    assert "careertracker_refresh" in response.headers.get("set-cookie", "")
    client.cookies.clear()
    assert client.post("/auth/refresh", headers=CSRF).status_code == 401


def test_reset_only_changes_the_owner_of_the_link(client, outbox):
    _register(client)
    _register(client, "other@example.com")
    _request(client)

    assert _confirm(client, _token_from(outbox[0][2])).status_code == 204
    assert _login(client, OLD_PASSWORD, "other@example.com").status_code == 200


def test_new_password_must_meet_the_length_rule(client, outbox):
    _register(client)
    _request(client)

    assert _confirm(client, _token_from(outbox[0][2]), "short").status_code == 422


def test_requests_per_email_are_limited(client, outbox):
    _register(client)

    statuses = [_request(client).status_code for _ in range(4)]

    assert statuses == [202, 202, 202, 429]
    assert len(outbox) == 3


def test_request_is_unavailable_without_outgoing_email(client, outbox, monkeypatch):
    monkeypatch.setenv("EMAIL_BACKEND", "disabled")
    _register(client)

    response = _request(client)

    assert response.status_code == 503
    assert response.json()["error_code"] == "password_reset_unavailable"
    assert outbox == []


def test_deleting_the_account_removes_its_reset_links(authenticated_client, outbox, db_session):
    _request(authenticated_client)

    response = authenticated_client.request("DELETE", "/auth/me", json={"password": OLD_PASSWORD})

    assert response.status_code == 204
    assert db_session.query(PasswordResetToken).count() == 0


# --- Giden e-posta ayarları ---------------------------------------------------------------


@pytest.fixture()
def production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    for name in ("EMAIL_BACKEND", "PUBLIC_APP_URL", "SMTP_HOST", "SMTP_FROM", "SMTP_PORT", "SMTP_SECURITY"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_production_without_email_settings_disables_reset(production):
    assert mailer.get_mail_settings().backend == "disabled"


def test_console_backend_is_refused_in_production(production):
    production.setenv("EMAIL_BACKEND", "console")

    with pytest.raises(RuntimeError, match="console"):
        mailer.validate_mail_configuration()


@pytest.mark.parametrize("missing", ["SMTP_HOST", "SMTP_FROM", "PUBLIC_APP_URL"])
def test_smtp_backend_needs_its_settings(production, missing):
    production.setenv("EMAIL_BACKEND", "smtp")
    for name, value in {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_FROM": "CareerTracker <bildirim@example.com>",
        "PUBLIC_APP_URL": "https://careertracker.example.com",
    }.items():
        if name != missing:
            production.setenv(name, value)

    with pytest.raises(RuntimeError):
        mailer.validate_mail_configuration()


class _FakeSmtp:
    instances = []

    def __init__(self, host, port, timeout=None, **_):
        self.host, self.port, self.calls = host, port, []
        _FakeSmtp.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def starttls(self, context=None):
        self.calls.append("starttls")

    def login(self, username, password):
        self.calls.append(("login", username))

    def send_message(self, message):
        self.calls.append(("send", message["To"], message["From"]))


def test_smtp_backend_uses_starttls_and_login(production):
    production.setenv("EMAIL_BACKEND", "smtp")
    production.setenv("SMTP_HOST", "smtp.example.com")
    production.setenv("SMTP_USERNAME", "apikey")
    production.setenv("SMTP_PASSWORD", "test-only-password")
    production.setenv("SMTP_FROM", "CareerTracker <bildirim@example.com>")
    production.setenv("PUBLIC_APP_URL", "https://careertracker.example.com/")
    production.setattr(mailer.smtplib, "SMTP", _FakeSmtp)
    _FakeSmtp.instances.clear()

    assert mailer.send_email("user@example.com", "Konu", "Gövde") is True

    [server] = _FakeSmtp.instances
    assert (server.host, server.port) == ("smtp.example.com", 587)
    assert server.calls == [
        "starttls",
        ("login", "apikey"),
        ("send", "user@example.com", "CareerTracker <bildirim@example.com>"),
    ]
    assert mailer.get_mail_settings().public_app_url == "https://careertracker.example.com"


def test_smtp_failure_does_not_raise(production):
    production.setenv("EMAIL_BACKEND", "smtp")
    production.setenv("SMTP_HOST", "smtp.example.com")
    production.setenv("SMTP_FROM", "bildirim@example.com")
    production.setenv("PUBLIC_APP_URL", "https://careertracker.example.com")

    def refuse(*_args, **_kwargs):
        raise ConnectionRefusedError()

    production.setattr(mailer.smtplib, "SMTP", refuse)

    assert mailer.send_email("user@example.com", "Konu", "Gövde") is False

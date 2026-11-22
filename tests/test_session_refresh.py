"""Kalıcı oturum: httpOnly yenileme çerezi, rotasyon, yeniden kullanım tespiti ve iptal."""

import hashlib
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from app.main import app
from app.models.refresh_tokens import RefreshToken
from app.models.users import User
from app.security import REFRESH_COOKIE_NAME
from app.services import session_service

CSRF = {"X-Requested-With": "CareerTracker"}
PASSWORD = "StrongPass123"


def login(client, email="owner@example.com", password=PASSWORD, remember_me=False):
    data = {"username": email, "password": password}
    if remember_me:
        data["remember_me"] = "true"
    return client.post("/auth/token", data=data)


def register_and_login(client, email="owner@example.com", remember_me=False):
    client.post("/auth/register", json={"email": email, "password": PASSWORD})
    response = login(client, email, remember_me=remember_me)
    assert response.status_code == 200
    return response


def refresh(client):
    return client.post("/auth/refresh", headers=CSRF)


def client_with_cookie(value):
    other = TestClient(app)
    other.cookies.set(REFRESH_COOKIE_NAME, value)
    return other


def test_login_sets_an_http_only_session_cookie(client):
    response = register_and_login(client)

    cookie = response.headers["set-cookie"].lower()
    assert f"{REFRESH_COOKIE_NAME}=" in cookie
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "path=/" in cookie
    # "Beni hatırla" yoksa çerez tarayıcı kapanınca silinir.
    assert "max-age" not in cookie


def test_remember_me_keeps_the_cookie_for_thirty_days(client):
    response = register_and_login(client, remember_me=True)

    assert "max-age=2592000" in response.headers["set-cookie"].lower()


def test_access_token_lives_fifteen_minutes(client):
    token = register_and_login(client).json()["access_token"]

    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["exp"] - claims["iat"] == 15 * 60


def test_only_a_hash_of_the_refresh_token_is_stored(client, db_session):
    register_and_login(client)
    raw = client.cookies.get(REFRESH_COOKIE_NAME)

    stored = db_session.query(RefreshToken).one()
    assert stored.token_hash == hashlib.sha256(raw.encode()).hexdigest()
    assert raw not in stored.token_hash


def test_refresh_rotates_the_cookie_and_returns_a_working_access_token(client):
    register_and_login(client)
    first = client.cookies.get(REFRESH_COOKIE_NAME)

    response = refresh(client)

    assert response.status_code == 200
    assert client.cookies.get(REFRESH_COOKIE_NAME) != first
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"})
    assert me.json()["email"] == "owner@example.com"


def test_refresh_keeps_remember_me_on_the_rotated_cookie(client):
    register_and_login(client, remember_me=True)

    response = refresh(client)

    assert "max-age=2592000" in response.headers["set-cookie"].lower()


def test_a_just_rotated_token_is_rejected_without_ending_the_session(client):
    register_and_login(client)
    old = client.cookies.get(REFRESH_COOKIE_NAME)
    assert refresh(client).status_code == 200

    # Aynı anda yenileyen ikinci sekme eski çerezi gönderir.
    late = refresh(client_with_cookie(old))

    assert late.status_code == 401
    assert late.json()["error_code"] == "refresh_token_rotated"
    assert "set-cookie" not in late.headers
    assert refresh(client).status_code == 200


def test_reusing_an_old_token_after_the_grace_period_revokes_the_whole_family(client, monkeypatch):
    register_and_login(client)
    old = client.cookies.get(REFRESH_COOKIE_NAME)
    assert refresh(client).status_code == 200
    monkeypatch.setattr(session_service, "ROTATION_GRACE", timedelta(0))

    reused = refresh(client_with_cookie(old))

    assert reused.status_code == 401
    assert reused.json()["error_code"] == "refresh_token_reused"
    # Saldırganın elindeki eski token tespit edildi; meşru oturum da güvenlik için kapanır.
    assert refresh(client).status_code == 401


def test_only_one_concurrent_rotation_can_claim_a_token(client, db_session):
    register_and_login(client)
    record = db_session.query(RefreshToken).one()
    now = datetime.now(timezone.utc)

    # Eş zamanlı iki istek aynı geçerli kaydı okumuş olsa bile yalnızca biri iptal edebilir.
    first = session_service.claim(db_session, record.id, now)
    second = session_service.claim(db_session, record.id, now)
    db_session.commit()

    assert (first, second) == (True, False)


def test_refresh_requires_the_csrf_header(client):
    register_and_login(client)

    response = client.post("/auth/refresh")

    assert response.status_code == 403
    assert response.json()["error_code"] == "csrf_header_missing"


def test_refresh_without_a_cookie_is_unauthorized(client):
    response = refresh(client)

    assert response.status_code == 401
    assert response.json()["error_code"] == "refresh_token_missing"


def test_an_unknown_cookie_is_rejected_and_cleared(client):
    response = refresh(client_with_cookie("not-a-real-token"))

    assert response.status_code == 401
    assert response.json()["error_code"] == "refresh_token_invalid"
    assert f'{REFRESH_COOKIE_NAME}=""' in response.headers["set-cookie"]


def test_an_expired_refresh_token_is_rejected(client, db_session):
    register_and_login(client)
    db_session.query(RefreshToken).update(
        {RefreshToken.expires_at: datetime.now(timezone.utc) - timedelta(minutes=1)}
    )
    db_session.commit()

    response = refresh(client)

    assert response.status_code == 401
    assert response.json()["error_code"] == "refresh_token_expired"


def test_a_deactivated_user_cannot_refresh(client, db_session):
    register_and_login(client)
    db_session.query(User).update({User.is_active: False})
    db_session.commit()

    assert refresh(client).status_code == 401


def test_logout_revokes_the_session_and_clears_the_cookie(client):
    register_and_login(client)
    old = client.cookies.get(REFRESH_COOKIE_NAME)

    response = client.post("/auth/logout", headers=CSRF)

    assert response.status_code == 204
    assert f'{REFRESH_COOKIE_NAME}=""' in response.headers["set-cookie"]
    assert refresh(client_with_cookie(old)).status_code == 401


def test_logout_requires_the_csrf_header(client):
    register_and_login(client)

    assert client.post("/auth/logout").status_code == 403
    assert refresh(client).status_code == 200


def test_password_change_ends_other_sessions_but_keeps_this_one(client):
    access = register_and_login(client, remember_me=True).json()["access_token"]
    other_device = TestClient(app)
    assert login(other_device).status_code == 200

    response = client.post(
        "/auth/me/password",
        headers={"Authorization": f"Bearer {access}"},
        json={"current_password": PASSWORD, "new_password": "NewStrongPass456"},
    )

    assert response.status_code == 204
    assert "max-age=2592000" in response.headers["set-cookie"].lower()
    assert refresh(other_device).status_code == 401
    assert refresh(client).status_code == 200


def test_account_deletion_removes_sessions_and_clears_the_cookie(client, db_session):
    access = register_and_login(client).json()["access_token"]

    response = client.request(
        "DELETE", "/auth/me", headers={"Authorization": f"Bearer {access}"}, json={"password": PASSWORD}
    )

    assert response.status_code == 204
    assert f'{REFRESH_COOKIE_NAME}=""' in response.headers["set-cookie"]
    assert db_session.query(RefreshToken).count() == 0


def test_refresh_tokens_of_one_user_do_not_work_for_another(client):
    register_and_login(client, email="first@example.com")
    first_cookie = client.cookies.get(REFRESH_COOKIE_NAME)
    second = TestClient(app)
    register_and_login(second, email="second@example.com")

    access = refresh(client_with_cookie(first_cookie)).json()["access_token"]

    me = second.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.json()["email"] == "first@example.com"

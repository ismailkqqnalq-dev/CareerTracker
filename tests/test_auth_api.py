import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import auth_service


def register(client, email="test@example.com", password="StrongPass123"):
    return client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )


def test_register_user_returns_public_data_only(client):
    response = register(client)

    assert response.status_code == 201
    assert response.json()["email"] == "test@example.com"
    assert "hashed_password" not in response.json()


def test_register_duplicate_email_returns_409(client):
    assert register(client).status_code == 201

    response = register(client, email="TEST@example.com")

    assert response.status_code == 409


def test_login_and_get_current_user(client):
    register(client)

    login_response = client.post(
        "/auth/token",
        data={
            "username": "test@example.com",
            "password": "StrongPass123",
        },
    )

    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert me_response.status_code == 200
    assert me_response.json()["email"] == "test@example.com"


def test_login_with_wrong_password_returns_401(client):
    register(client)

    response = client.post(
        "/auth/token",
        data={
            "username": "test@example.com",
            "password": "WrongPassword123",
        },
    )

    assert response.status_code == 401


def test_me_without_token_returns_401(client):
    response = client.get("/auth/me")

    assert response.status_code == 401

@pytest.mark.parametrize(
    "bad_secret",
    ["", "short", "x" * 31, "replace-with-a-random-secret"],
)
def test_app_rejects_invalid_jwt_secret_at_startup(monkeypatch, bad_secret):
    monkeypatch.setenv("JWT_SECRET_KEY", bad_secret)

    with pytest.raises(RuntimeError) as error:
        with TestClient(app):
            pass

    assert "JWT_SECRET_KEY" in str(error.value)
    if bad_secret:
        assert bad_secret not in str(error.value)


def test_app_accepts_a_32_byte_jwt_secret_at_startup(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 32)

    with TestClient(app) as test_client:
        assert test_client.get("/").status_code == 200


def test_registration_disabled_returns_structured_403(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("REGISTRATION_ENABLED", raising=False)

    response = register(client)

    assert response.status_code == 403
    assert response.json()["error_code"] == "registration_disabled"


def test_registration_can_be_explicitly_enabled_in_production(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("REGISTRATION_ENABLED", "true")

    assert register(client).status_code == 201


def test_login_verifies_a_dummy_hash_for_unknown_email(client, monkeypatch):
    calls = []

    def record_verification(password, encoded_hash):
        calls.append((password, encoded_hash))
        return False

    monkeypatch.setattr(auth_service, "verify_password", record_verification)
    response = client.post(
        "/auth/token",
        data={"username": "missing@example.com", "password": "WrongPass123"},
    )

    assert response.status_code == 401
    assert len(calls) == 1
    assert calls[0][0] == "WrongPass123"
    assert calls[0][1]


def test_login_verifies_stored_hash_for_existing_user(client, monkeypatch):
    assert register(client).status_code == 201
    calls = []

    def record_verification(password, encoded_hash):
        calls.append((password, encoded_hash))
        return True

    monkeypatch.setattr(auth_service, "verify_password", record_verification)
    response = client.post(
        "/auth/token",
        data={"username": "test@example.com", "password": "StrongPass123"},
    )

    assert response.status_code == 200
    assert len(calls) == 1
    assert calls[0][0] == "StrongPass123"
    assert calls[0][1]

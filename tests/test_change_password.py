"""POST /auth/me/password: giriş yapmış kullanıcı mevcut şifresini doğrulayarak şifresini değiştirir."""


def login(client, password):
    return client.post(
        "/auth/token",
        data={"username": "owner@example.com", "password": password},
    )


def test_change_password_replaces_the_old_password(authenticated_client):
    response = authenticated_client.post(
        "/auth/me/password",
        json={"current_password": "StrongPass123", "new_password": "NewStrongPass456"},
    )

    assert response.status_code == 204
    assert login(authenticated_client, "StrongPass123").status_code == 401
    assert login(authenticated_client, "NewStrongPass456").status_code == 200


def test_change_password_rejects_a_wrong_current_password(authenticated_client):
    response = authenticated_client.post(
        "/auth/me/password",
        json={"current_password": "WrongPass123", "new_password": "NewStrongPass456"},
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "password_confirmation_failed"
    assert login(authenticated_client, "StrongPass123").status_code == 200
    assert login(authenticated_client, "NewStrongPass456").status_code == 401


def test_change_password_rejects_a_too_short_new_password(authenticated_client):
    response = authenticated_client.post(
        "/auth/me/password",
        json={"current_password": "StrongPass123", "new_password": "short"},
    )

    assert response.status_code == 422
    assert login(authenticated_client, "StrongPass123").status_code == 200


def test_change_password_only_affects_the_current_user(authenticated_client):
    authenticated_client.post(
        "/auth/register",
        json={"email": "other@example.com", "password": "OtherPass123"},
    )

    authenticated_client.post(
        "/auth/me/password",
        json={"current_password": "StrongPass123", "new_password": "NewStrongPass456"},
    )

    other_login = authenticated_client.post(
        "/auth/token",
        data={"username": "other@example.com", "password": "OtherPass123"},
    )
    assert other_login.status_code == 200


def test_change_password_requires_authentication(client):
    response = client.post(
        "/auth/me/password",
        json={"current_password": "StrongPass123", "new_password": "NewStrongPass456"},
    )

    assert response.status_code == 401

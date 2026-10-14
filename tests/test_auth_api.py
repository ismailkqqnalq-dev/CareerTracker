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
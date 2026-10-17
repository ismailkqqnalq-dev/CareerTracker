import pytest


@pytest.fixture()
def skill_id(authenticated_client):
    response = authenticated_client.post(
        "/skills",
        json={"name": "Python", "category": "language"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_add_profile_skill(authenticated_client, skill_id):
    response = authenticated_client.post(
        "/users/me/skills",
        json={
            "skill_id": skill_id,
            "proficiency_level": "intermediate",
            "years_experience": 2.5,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["skill_id"] == skill_id
    assert body["proficiency_level"] == "intermediate"
    assert body["years_experience"] == 2.5

    listed = authenticated_client.get("/users/me/skills")
    assert listed.status_code == 200
    assert listed.json() == [body]


def test_profile_skill_defaults(authenticated_client, skill_id):
    response = authenticated_client.post(
        "/users/me/skills",
        json={"skill_id": skill_id},
    )

    assert response.status_code == 201
    assert response.json()["proficiency_level"] == "beginner"
    assert response.json()["years_experience"] == 0


def test_duplicate_profile_skill_returns_409(
    authenticated_client, skill_id
):
    payload = {"skill_id": skill_id}
    assert authenticated_client.post(
        "/users/me/skills", json=payload
    ).status_code == 201

    response = authenticated_client.post(
        "/users/me/skills", json=payload
    )

    assert response.status_code == 409
    listed = authenticated_client.get("/users/me/skills")
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_unknown_profile_skill_returns_404(authenticated_client):
    response = authenticated_client.post(
        "/users/me/skills",
        json={"skill_id": 999999},
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "extra_fields",
    [
        {"proficiency_level": "master"},
        {"years_experience": -1},
    ],
)
def test_invalid_profile_skill_returns_422(
    authenticated_client, skill_id, extra_fields
):
    response = authenticated_client.post(
        "/users/me/skills",
        json={"skill_id": skill_id, **extra_fields},
    )

    assert response.status_code == 422
    listed = authenticated_client.get("/users/me/skills")
    assert listed.status_code == 200
    assert listed.json() == []


def test_profile_skills_require_login(client):
    assert client.get("/users/me/skills").status_code == 401
    assert client.post(
        "/users/me/skills",
        json={"skill_id": 1},
    ).status_code == 401


def test_profile_skills_are_private(authenticated_client, skill_id):
    client = authenticated_client

    owner_response = client.post(
        "/users/me/skills",
        json={"skill_id": skill_id},
    )
    assert owner_response.status_code == 201

    registration = client.post(
        "/auth/register",
        json={
            "email": "second@example.com",
            "password": "StrongPass123",
        },
    )
    assert registration.status_code == 201

    login = client.post(
        "/auth/token",
        data={
            "username": "second@example.com",
            "password": "StrongPass123",
        },
    )
    assert login.status_code == 200
    second_user_headers = {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }

    listed = client.get(
        "/users/me/skills",
        headers=second_user_headers,
    )
    assert listed.status_code == 200
    assert listed.json() == []

    # Aynı katalog becerisi farklı kullanıcıların profilinde bulunabilir.
    second_response = client.post(
        "/users/me/skills",
        headers=second_user_headers,
        json={
            "skill_id": skill_id,
            "proficiency_level": "advanced",
        },
    )
    assert second_response.status_code == 201
    assert second_response.json()["id"] != owner_response.json()["id"]

    second_list = client.get(
        "/users/me/skills",
        headers=second_user_headers,
    )
    assert second_list.status_code == 200
    assert second_list.json() == [second_response.json()]

    # İstek bazındaki ikinci kullanıcı token'ı, asıl oturumu değiştirmez.
    owner_list = client.get("/users/me/skills")
    assert owner_list.status_code == 200
    assert owner_list.json() == [owner_response.json()]
    
def test_update_profile_skill(authenticated_client, skill_id):
    created = authenticated_client.post(
        "/users/me/skills",
        json={"skill_id": skill_id},
    )
    user_skill_id = created.json()["id"]

    response = authenticated_client.patch(
        f"/users/me/skills/{user_skill_id}",
        json={
            "proficiency_level": "advanced",
            "years_experience": 3.5,
        },
    )

    assert response.status_code == 200
    assert response.json()["proficiency_level"] == "advanced"
    assert response.json()["years_experience"] == 3.5


def test_empty_profile_skill_update_returns_422(
    authenticated_client, skill_id
):
    created = authenticated_client.post(
        "/users/me/skills",
        json={"skill_id": skill_id},
    )
    user_skill_id = created.json()["id"]

    response = authenticated_client.patch(
        f"/users/me/skills/{user_skill_id}",
        json={},
    )

    assert response.status_code == 422


def test_user_cannot_update_another_users_profile_skill(
    authenticated_client, skill_id
):
    client = authenticated_client
    created = client.post(
        "/users/me/skills",
        json={"skill_id": skill_id},
    )
    user_skill_id = created.json()["id"]

    client.post(
        "/auth/register",
        json={
            "email": "second@example.com",
            "password": "StrongPass123",
        },
    )
    login = client.post(
        "/auth/token",
        data={
            "username": "second@example.com",
            "password": "StrongPass123",
        },
    )
    second_user_headers = {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }

    response = client.patch(
        f"/users/me/skills/{user_skill_id}",
        headers=second_user_headers,
        json={"proficiency_level": "expert"},
    )

    assert response.status_code == 404

    owner_list = client.get("/users/me/skills")
    assert owner_list.status_code == 200
    assert owner_list.json()[0]["proficiency_level"] == "beginner"


def test_delete_profile_skill(authenticated_client, skill_id):
    created = authenticated_client.post(
        "/users/me/skills",
        json={"skill_id": skill_id},
    )
    user_skill_id = created.json()["id"]

    response = authenticated_client.delete(
        f"/users/me/skills/{user_skill_id}"
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Profile skill deleted successfully"
    assert authenticated_client.get("/users/me/skills").json() == []

    missing = authenticated_client.delete(
        f"/users/me/skills/{user_skill_id}"
    )
    assert missing.status_code == 404


def test_user_cannot_delete_another_users_profile_skill(
    authenticated_client, skill_id
):
    client = authenticated_client
    created = client.post(
        "/users/me/skills",
        json={"skill_id": skill_id},
    )
    user_skill_id = created.json()["id"]

    client.post(
        "/auth/register",
        json={
            "email": "second@example.com",
            "password": "StrongPass123",
        },
    )
    login = client.post(
        "/auth/token",
        data={
            "username": "second@example.com",
            "password": "StrongPass123",
        },
    )
    second_user_headers = {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }

    response = client.delete(
        f"/users/me/skills/{user_skill_id}",
        headers=second_user_headers,
    )

    assert response.status_code == 404
    assert client.get("/users/me/skills").json() == [created.json()]
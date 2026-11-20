"""Başvuruyu, ilan analizinde bulunan becerilerle tek istekte kaydetme."""

from app.models.skills import Skill


def _opportunity_payload(**overrides):
    payload = {
        "company": "Örnek Teknoloji",
        "position": "Backend Developer",
        "type": "İş",
        "application_date": "2026-11-20",
        "job_link": "",
        "salary": 0,
        "location": "İstanbul",
        "status": "Başvuruldu",
        "notes": "",
        "next_action": "",
        "last_contact_date": "2026-11-20",
    }
    payload.update(overrides)
    return payload


def _shared_skill(db_session, name):
    skill = Skill(name=name, category="tool")
    db_session.add(skill)
    db_session.commit()
    return skill.id


def _private_skill(client, name, headers=None):
    response = client.post(
        "/skills", json={"name": name, "category": "tool"}, headers=headers
    )
    assert response.status_code == 201
    return response.json()["id"]


def _other_user_headers(client):
    credentials = {"email": "other@example.com", "password": "StrongPass123"}
    assert client.post("/auth/register", json=credentials).status_code == 201
    login = client.post(
        "/auth/token",
        data={"username": credentials["email"], "password": credentials["password"]},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _attached_skill_ids(client, opportunity_id):
    response = client.get(f"/opportunities/{opportunity_id}/skills")
    assert response.status_code == 200
    return sorted(skill["id"] for skill in response.json())


def test_create_attaches_shared_and_own_private_skills(authenticated_client, db_session):
    client = authenticated_client
    shared_id = _shared_skill(db_session, "SharedCreateSkill")
    private_id = _private_skill(client, "OwnPrivateCreateSkill")

    response = client.post(
        "/opportunities",
        json=_opportunity_payload(skill_ids=[shared_id, private_id]),
    )

    assert response.status_code == 200
    assert "skill_ids" not in response.json()
    assert _attached_skill_ids(client, response.json()["id"]) == sorted(
        [shared_id, private_id]
    )


def test_create_attaches_a_repeated_skill_id_once(authenticated_client, db_session):
    client = authenticated_client
    shared_id = _shared_skill(db_session, "RepeatedCreateSkill")

    response = client.post(
        "/opportunities",
        json=_opportunity_payload(skill_ids=[shared_id, shared_id]),
    )

    assert response.status_code == 200
    assert _attached_skill_ids(client, response.json()["id"]) == [shared_id]


def test_create_rejects_another_users_private_skill_and_saves_nothing(
    authenticated_client,
):
    client = authenticated_client
    other_headers = _other_user_headers(client)
    foreign_id = _private_skill(client, "ForeignPrivateSkill", headers=other_headers)

    response = client.post(
        "/opportunities", json=_opportunity_payload(skill_ids=[foreign_id])
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "unknown_skill"
    assert client.get("/opportunities").json() == []


def test_create_rejects_a_missing_skill_id_and_saves_nothing(
    authenticated_client, db_session
):
    client = authenticated_client
    shared_id = _shared_skill(db_session, "ExistingCreateSkill")

    response = client.post(
        "/opportunities",
        json=_opportunity_payload(skill_ids=[shared_id, 999_999]),
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "unknown_skill"
    assert client.get("/opportunities").json() == []


def test_create_limits_the_number_of_skill_ids(authenticated_client):
    response = authenticated_client.post(
        "/opportunities",
        json=_opportunity_payload(skill_ids=list(range(1, 102))),
    )

    assert response.status_code == 422


def test_create_without_skill_ids_attaches_nothing(authenticated_client):
    client = authenticated_client

    response = client.post("/opportunities", json=_opportunity_payload())

    assert response.status_code == 200
    assert _attached_skill_ids(client, response.json()["id"]) == []

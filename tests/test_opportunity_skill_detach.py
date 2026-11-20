"""Başvuruya bağlanmış bir beceriyi kaldırma."""

from app.models.skills import Skill


def _create_opportunity(client, headers=None):
    response = client.post(
        "/opportunities",
        json={
            "company": "Örnek Teknoloji",
            "position": "Backend Developer",
            "type": "İş",
            "application_date": "2026-11-20",
            "job_link": "",
            "salary": 0,
            "location": "İzmir",
            "status": "Başvuruldu",
            "notes": "",
            "next_action": "",
            "last_contact_date": "2026-11-20",
        },
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()["id"]


def _skill(client, name, headers=None):
    # POST /skills alias'ı da oluşturur; böylece beceri adıyla bağlanabilir.
    response = client.post(
        "/skills", json={"name": name, "category": "tool"}, headers=headers
    )
    assert response.status_code == 201
    return response.json()["id"]


def _attach(client, opportunity_id, skill_name, headers=None):
    response = client.post(
        f"/opportunities/{opportunity_id}/skills",
        json={"skill": skill_name},
        headers=headers,
    )
    assert response.status_code == 201


def _attached_names(client, opportunity_id, headers=None):
    response = client.get(f"/opportunities/{opportunity_id}/skills", headers=headers)
    assert response.status_code == 200
    return [skill["name"] for skill in response.json()]


def _other_user_headers(client):
    credentials = {"email": "other@example.com", "password": "StrongPass123"}
    assert client.post("/auth/register", json=credentials).status_code == 201
    login = client.post(
        "/auth/token",
        data={"username": credentials["email"], "password": credentials["password"]},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_detach_removes_only_that_skill_and_keeps_it_in_the_catalog(
    authenticated_client, db_session
):
    client = authenticated_client
    keep_id = _skill(client, "KeepDetachSkill")
    remove_id = _skill(client, "RemoveDetachSkill")
    opportunity_id = _create_opportunity(client)
    _attach(client, opportunity_id, "KeepDetachSkill")
    _attach(client, opportunity_id, "RemoveDetachSkill")

    response = client.delete(f"/opportunities/{opportunity_id}/skills/{remove_id}")

    assert response.status_code == 204
    assert _attached_names(client, opportunity_id) == ["KeepDetachSkill"]
    assert db_session.get(Skill, remove_id) is not None
    assert db_session.get(Skill, keep_id) is not None


def test_detach_reports_a_skill_that_is_not_attached(authenticated_client):
    client = authenticated_client
    skill_id = _skill(client, "NeverAttachedSkill")
    opportunity_id = _create_opportunity(client)

    response = client.delete(f"/opportunities/{opportunity_id}/skills/{skill_id}")

    assert response.status_code == 404
    assert response.json()["error_code"] == "skill_not_attached"


def test_detach_cannot_touch_another_users_opportunity(authenticated_client):
    client = authenticated_client
    other_headers = _other_user_headers(client)
    skill_id = _skill(client, "ForeignDetachSkill", headers=other_headers)
    foreign_opportunity = _create_opportunity(client, headers=other_headers)
    _attach(client, foreign_opportunity, "ForeignDetachSkill", headers=other_headers)

    response = client.delete(f"/opportunities/{foreign_opportunity}/skills/{skill_id}")

    assert response.status_code == 404
    assert response.json()["error_code"] == "opportunity_not_found"
    assert _attached_names(client, foreign_opportunity, headers=other_headers) == [
        "ForeignDetachSkill"
    ]

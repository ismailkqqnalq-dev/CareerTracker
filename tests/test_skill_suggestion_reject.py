"""Bekleyen bir beceri önerisini reddetme."""

from app.models.skills import Skill


def _suggest(client, name, headers=None):
    response = client.post("/skills/suggestions", json={"skill": name}, headers=headers)
    assert response.status_code in (200, 201)
    return response.json()["id"]


def _pending_ids(client):
    response = client.get("/skills/suggestions?status=pending")
    assert response.status_code == 200
    return [item["id"] for item in response.json()]


def _other_user_headers(client):
    credentials = {"email": "other@example.com", "password": "StrongPass123"}
    assert client.post("/auth/register", json=credentials).status_code == 201
    login = client.post(
        "/auth/token",
        data={"username": credentials["email"], "password": credentials["password"]},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_reject_marks_a_pending_suggestion_rejected(authenticated_client):
    client = authenticated_client
    suggestion_id = _suggest(client, "Belirsiz Araç")

    response = client.post(f"/skills/suggestions/{suggestion_id}/reject")

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert response.json()["resolved_skill_id"] is None
    assert suggestion_id not in _pending_ids(client)


def test_reject_refuses_an_already_accepted_suggestion(authenticated_client, db_session):
    client = authenticated_client
    skill = Skill(name="AcceptedTarget", category="tool")
    db_session.add(skill)
    db_session.commit()
    suggestion_id = _suggest(client, "Kabul Edilecek Araç")
    resolved = client.patch(
        f"/skills/suggestions/{suggestion_id}", json={"skill_id": skill.id}
    )
    assert resolved.status_code == 200

    response = client.post(f"/skills/suggestions/{suggestion_id}/reject")

    assert response.status_code == 409
    assert response.json()["error_code"] == "suggestion_not_pending"


def test_reject_cannot_touch_another_users_suggestion(authenticated_client):
    client = authenticated_client
    other_headers = _other_user_headers(client)
    foreign_id = _suggest(client, "Yabancı Öneri", headers=other_headers)

    response = client.post(f"/skills/suggestions/{foreign_id}/reject")

    assert response.status_code == 404
    still_pending = client.get(
        "/skills/suggestions?status=pending", headers=other_headers
    ).json()
    assert [item["id"] for item in still_pending] == [foreign_id]

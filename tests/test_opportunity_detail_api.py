"""GET /opportunities/{id}/detail: başvurunun bağlı kayıtları tek istekte ve yalnızca sahibine."""

from app.models.tasks import Task
from app.models.users import User


def create_opportunity(client, company="Trendyol", skill_ids=()):
    response = client.post("/opportunities", json={
        "company": company, "position": "Backend", "type": "İş", "application_date": "2026-11-01",
        "job_link": "https://example.test/ilan", "salary": 0, "location": "İzmir", "status": "Teknik mülakat",
        "notes": "Takım lideriyle görüşüldü", "next_action": "Vaka çalışmasını gönder",
        "last_contact_date": "2026-11-10", "skill_ids": list(skill_ids),
    })
    assert response.status_code == 200, response.text
    return response.json()["id"]


def post(client, path, body):
    response = client.post(path, json=body)
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_returns_the_opportunity_with_its_related_records_in_order(authenticated_client):
    client = authenticated_client
    skill = client.post("/skills", json={"name": "Detaytest", "category": "tool"}).json()["id"]
    opportunity_id = create_opportunity(client, skill_ids=[skill])
    contact = post(client, "/contacts", {
        "name": "Ayşe Yılmaz", "role": "İK", "email": "ayse@example.test",
        "linkedin": "https://www.linkedin.com/in/ayse", "opportunity_id": opportunity_id,
    })
    post(client, "/tasks", {"opportunity_id": opportunity_id, "description": "Sonra", "due_date": "2026-11-30"})
    post(client, "/tasks", {"opportunity_id": opportunity_id, "description": "Önce", "due_date": "2026-11-21"})
    post(client, "/tasks", {"opportunity_id": opportunity_id, "description": "Bitti", "due_date": "2026-11-01", "is_completed": True})
    post(client, "/activities", {"opportunity_id": opportunity_id, "contact_id": contact, "activity_type": "Görüşme",
                                 "dates": "2026-11-05", "notes": "İlk görüşme"})
    post(client, "/activities", {"opportunity_id": opportunity_id, "activity_type": "E-posta",
                                 "dates": "2026-11-10", "notes": "Teşekkür"})

    response = client.get(f"/opportunities/{opportunity_id}/detail")

    assert response.status_code == 200
    detail = response.json()
    assert detail["opportunity"]["company"] == "Trendyol"
    assert [item["name"] for item in detail["contacts"]] == ["Ayşe Yılmaz"]
    assert [item["description"] for item in detail["tasks"]] == ["Önce", "Sonra", "Bitti"]
    assert [item["activity_type"] for item in detail["activities"]] == ["E-posta", "Görüşme"]
    assert detail["activities"][1]["contact_id"] == contact
    assert detail["skills"] == [{"id": skill, "name": "Detaytest"}]


def test_does_not_include_records_of_other_opportunities(authenticated_client):
    first = create_opportunity(authenticated_client, "Birinci")
    second = create_opportunity(authenticated_client, "İkinci")
    post(authenticated_client, "/tasks", {"opportunity_id": second, "description": "Başkasının", "due_date": "2026-11-21"})

    detail = authenticated_client.get(f"/opportunities/{first}/detail").json()

    assert detail["tasks"] == []


def test_ignores_another_users_rows_even_if_linked_to_this_opportunity(authenticated_client, db_session):
    opportunity_id = create_opportunity(authenticated_client)
    other = User(email="other@example.com", hashed_password="x")
    db_session.add(other)
    db_session.commit()
    # API buna izin vermez; satır doğrudan eklenerek kullanıcı süzgecinin varlığı sınanır.
    db_session.add(Task(user_id=other.id, opportunity_id=opportunity_id, description="Sızmamalı"))
    db_session.commit()

    detail = authenticated_client.get(f"/opportunities/{opportunity_id}/detail").json()

    assert detail["tasks"] == []


def test_another_users_opportunity_is_not_found(authenticated_client):
    authenticated_client.post("/auth/register", json={"email": "other@example.com", "password": "OtherPass123"})
    token = authenticated_client.post(
        "/auth/token", data={"username": "other@example.com", "password": "OtherPass123"}
    ).json()["access_token"]
    foreign = authenticated_client.post("/opportunities", headers={"Authorization": f"Bearer {token}"}, json={
        "company": "Gizli", "position": "Backend", "type": "İş", "application_date": "2026-11-01",
        "job_link": "", "salary": 0, "location": "İzmir", "status": "Başvuruldu", "notes": "",
        "next_action": "", "last_contact_date": "2026-11-10",
    }).json()["id"]

    response = authenticated_client.get(f"/opportunities/{foreign}/detail")

    assert response.status_code == 404
    assert "Gizli" not in response.text


def test_unknown_opportunity_is_not_found(authenticated_client):
    assert authenticated_client.get("/opportunities/999999/detail").status_code == 404


def test_requires_authentication(client):
    assert client.get("/opportunities/1/detail").status_code == 401

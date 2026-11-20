"""Genel bakıştaki gündem: yaklaşan/geciken görevler ve takip zamanı gelen başvurular."""

TODAY = "2026-11-20"


def _opportunity(client, company, status="Başvuruldu", last_contact="2026-11-01",
                 next_action="", headers=None):
    response = client.post(
        "/opportunities",
        json={
            "company": company,
            "position": "Backend Developer",
            "type": "İş",
            "application_date": "2026-11-01",
            "job_link": "",
            "salary": 0,
            "location": "İzmir",
            "status": status,
            "notes": "",
            "next_action": next_action,
            "last_contact_date": last_contact,
        },
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()["id"]


def _task(client, opportunity_id, description, due_date, is_completed=False, headers=None):
    response = client.post(
        "/tasks",
        json={
            "opportunity_id": opportunity_id,
            "description": description,
            "due_date": due_date,
            "is_completed": is_completed,
        },
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()["id"]


def _other_user_headers(client):
    credentials = {"email": "other@example.com", "password": "StrongPass123"}
    assert client.post("/auth/register", json=credentials).status_code == 201
    login = client.post(
        "/auth/token",
        data={"username": credentials["email"], "password": credentials["password"]},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _agenda(client, today=TODAY):
    response = client.get("/agenda", params={"today": today})
    assert response.status_code == 200
    return response.json()


def test_agenda_lists_open_tasks_due_within_a_week_sorted_by_date(authenticated_client):
    client = authenticated_client
    opportunity_id = _opportunity(client, "Örnek AŞ", last_contact=TODAY)
    _task(client, opportunity_id, "bu hafta", "2026-11-27")
    _task(client, opportunity_id, "gecikmiş", "2026-11-15")
    _task(client, opportunity_id, "bugün", TODAY)
    _task(client, opportunity_id, "çok ileride", "2026-11-28")
    _task(client, opportunity_id, "bitmiş", "2026-11-18", is_completed=True)

    tasks = _agenda(client)["tasks"]

    assert [task["description"] for task in tasks] == ["gecikmiş", "bugün", "bu hafta"]
    assert tasks[0]["due_date"] == "2026-11-15"
    assert tasks[0]["company"] == "Örnek AŞ"
    assert tasks[0]["position"] == "Backend Developer"
    assert tasks[0]["opportunity_id"] == opportunity_id


def test_agenda_lists_active_opportunities_without_recent_contact(authenticated_client):
    client = authenticated_client
    _opportunity(client, "Sessiz AŞ", last_contact="2026-11-05", next_action="Teşekkür e-postası at")
    _opportunity(client, "Mülakatçı AŞ", status="teknik MÜLAKAT", last_contact="2026-11-10")
    _opportunity(client, "Yeni Temas AŞ", last_contact="2026-11-15")
    _opportunity(client, "Teklif AŞ", status="Teklif", last_contact="2026-10-01")
    _opportunity(client, "Ret AŞ", status="Reddedildi", last_contact="2026-10-01")

    follow_ups = _agenda(client)["follow_ups"]

    assert [item["company"] for item in follow_ups] == ["Sessiz AŞ", "Mülakatçı AŞ"]
    assert follow_ups[0]["days_since_contact"] == 15
    assert follow_ups[0]["next_action"] == "Teşekkür e-postası at"
    assert follow_ups[0]["last_contact_date"] == "2026-11-05"
    assert follow_ups[1]["days_since_contact"] == 10


def test_agenda_uses_the_callers_today_not_the_servers(authenticated_client):
    client = authenticated_client
    _opportunity(client, "Sınırda AŞ", last_contact="2026-11-13")

    assert [item["company"] for item in _agenda(client, "2026-11-19")["follow_ups"]] == []
    assert [item["company"] for item in _agenda(client, "2026-11-20")["follow_ups"]] == ["Sınırda AŞ"]


def test_agenda_shows_only_the_callers_records(authenticated_client):
    client = authenticated_client
    other_headers = _other_user_headers(client)
    foreign_opportunity = _opportunity(client, "Yabancı AŞ", headers=other_headers)
    _task(client, foreign_opportunity, "yabancı görev", TODAY, headers=other_headers)

    agenda = _agenda(client)

    assert agenda == {"tasks": [], "follow_ups": []}


def test_agenda_rejects_an_invalid_date(authenticated_client):
    response = authenticated_client.get("/agenda", params={"today": "20-11-2026"})

    assert response.status_code == 422


def test_agenda_requires_login(client):
    assert client.get("/agenda", params={"today": TODAY}).status_code == 401

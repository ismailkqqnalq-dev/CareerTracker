import pytest


def _opportunity(client, company, **extra):
    response = client.post("/opportunities", json={"company": company, "position": "Backend", **extra})
    assert response.status_code == 200, response.text
    return response.json()


def test_opportunity_needs_only_company_and_position(authenticated_client):
    created = _opportunity(authenticated_client, "Hızlı AŞ")

    assert created["status"] == "Başvuruldu"
    for field in ("type", "application_date", "job_link", "salary", "location", "notes", "next_action", "last_contact_date"):
        assert created[field] is None
    dashboard = authenticated_client.get("/dashboard").json()
    assert dashboard["total_opportunities"] == 1
    agenda = authenticated_client.get("/agenda?today=2026-11-23")
    assert agenda.status_code == 200
    assert authenticated_client.get("/opportunities/export").status_code == 200


@pytest.mark.parametrize("missing", ["company", "position"])
def test_opportunity_still_requires_company_and_position(authenticated_client, missing):
    payload = {"company": "Eksik AŞ", "position": "Backend"}
    del payload[missing]

    assert authenticated_client.post("/opportunities", json=payload).status_code == 422


def test_invalid_job_link_is_still_rejected(authenticated_client):
    response = authenticated_client.post(
        "/opportunities", json={"company": "Link AŞ", "position": "Backend", "job_link": "javascript:alert(1)"}
    )

    assert response.status_code == 422


def test_contact_needs_only_name_and_opportunity(authenticated_client):
    opportunity = _opportunity(authenticated_client, "Kişi AŞ")

    response = authenticated_client.post("/contacts", json={"name": "Ayşe", "opportunity_id": opportunity["id"]})

    assert response.status_code == 200, response.text
    assert (response.json()["role"], response.json()["email"], response.json()["linkedin"]) == (None, None, None)


def test_activity_notes_are_optional(authenticated_client):
    opportunity = _opportunity(authenticated_client, "Aktivite AŞ")

    response = authenticated_client.post(
        "/activities",
        json={"opportunity_id": opportunity["id"], "activity_type": "Görüşme", "dates": "2026-11-23"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["notes"] is None


def _ids(client, path):
    response = client.get(path)
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()], int(response.headers["X-Total-Count"])


def test_newest_order_puts_latest_records_on_the_first_page(authenticated_client):
    client = authenticated_client
    created = [_opportunity(client, f"Şirket {index}")["id"] for index in range(5)]
    for opportunity_id in created:
        client.post("/tasks", json={"opportunity_id": opportunity_id, "description": "Takip", "due_date": "2026-12-01"})
        client.post("/contacts", json={"name": "Kişi", "opportunity_id": opportunity_id})
        client.post("/activities", json={"opportunity_id": opportunity_id, "activity_type": "E-posta", "dates": "2026-11-23"})

    for path in ("/opportunities", "/tasks", "/contacts", "/activities"):
        oldest, total = _ids(client, f"{path}?limit=2")
        newest, newest_total = _ids(client, f"{path}?limit=2&order=newest")
        second_page, _ = _ids(client, f"{path}?limit=2&offset=2&order=newest")
        all_ids = sorted(_ids(client, f"{path}?limit=200")[0])
        assert total == newest_total == 5
        assert oldest == all_ids[:2]
        assert newest == [all_ids[-1], all_ids[-2]]
        assert second_page == [all_ids[-3], all_ids[-4]]


def test_newest_order_combines_with_search(authenticated_client):
    client = authenticated_client
    for company in ("Alfa", "Beta", "Alfa İkinci"):
        _opportunity(client, company)

    response = client.get("/opportunities?q=alfa&order=newest")

    assert [item["company"] for item in response.json()] == ["Alfa İkinci", "Alfa"]


def test_unknown_order_value_is_rejected(authenticated_client):
    assert authenticated_client.get("/opportunities?order=random").status_code == 422

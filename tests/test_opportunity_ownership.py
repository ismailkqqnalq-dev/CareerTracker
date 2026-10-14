import csv
import io

import pytest


@pytest.fixture
def owned_opportunity(authenticated_client):
    response = authenticated_client.post(
        "/opportunities",
        json={
            "company": "Owner Company",
            "position": "Backend Developer",
            "type": "staj",
            "application_date": "2026-10-14",
            "job_link": "https://example.com/job",
            "salary": 10000,
            "location": "İstanbul",
            "status": "Başvuruldu",
            "notes": "Private note",
            "next_action": "Takip et",
            "last_contact_date": "2026-10-14",
        },
    )
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def other_user_headers(client):
    registration = client.post(
        "/auth/register",
        json={
            "email": "other@example.com",
            "password": "StrongPass123",
        },
    )
    assert registration.status_code == 201

    login = client.post(
        "/auth/token",
        data={
            "username": "other@example.com",
            "password": "StrongPass123",
        },
    )
    assert login.status_code == 200

    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_other_user_cannot_access_opportunity(
    authenticated_client,
    owned_opportunity,
    other_user_headers,
    method,
):
    url = f"/opportunities/{owned_opportunity['id']}"
    request_options = {"headers": other_user_headers}

    if method == "PATCH":
        request_options["json"] = {"company": "Unauthorized change"}

    response = authenticated_client.request(method, url, **request_options)

    assert response.status_code == 404

    # Kayıt sahibinin erişimi sürmeli; kayıt değişmemiş olmalı.
    owner_response = authenticated_client.get(url)
    assert owner_response.status_code == 200
    assert owner_response.json() == owned_opportunity


def test_other_user_cannot_see_opportunity_in_lists_or_reports(
    authenticated_client,
    owned_opportunity,
    other_user_headers,
):
    listed = authenticated_client.get(
        "/opportunities",
        headers=other_user_headers,
    )
    assert listed.status_code == 200
    assert listed.json() == []

    dashboard = authenticated_client.get(
        "/dashboard",
        headers=other_user_headers,
    )
    assert dashboard.status_code == 200
    assert dashboard.json() == {
        "total_opportunities": 0,
        "by_status": {},
        "by_company": {},
        "interview_count": 0,
        "offer_count": 0,
        "rejection_rate": 0,
    }

    exported = authenticated_client.get(
        "/opportunities/export",
        headers=other_user_headers,
    )
    assert exported.status_code == 200

    rows = list(csv.reader(io.StringIO(exported.text.lstrip("\ufeff"))))
    assert rows == [[
        "id",
        "company",
        "position",
        "type",
        "status",
        "salary",
        "location",
        "application_date",
    ]]


def test_opportunities_without_token_returns_401(client):
    response = client.get("/opportunities")

    assert response.status_code == 401
    
@pytest.mark.parametrize("method", ["GET", "POST"])
def test_other_user_cannot_read_or_attach_opportunity_skills(
    authenticated_client,
    owned_opportunity,
    other_user_headers,
    method,
):
    for name in ("Python", "SQL"):
        created = authenticated_client.post(
            "/skills",
            json={"name": name, "category": "language"},
        )
        assert created.status_code == 201

    url = f"/opportunities/{owned_opportunity['id']}/skills"

    # Kayıt sahibi kendi fırsatına beceri ekleyebilmeli.
    attached = authenticated_client.post(url, json={"skill": "Python"})
    assert attached.status_code == 201

    request_options = {"headers": other_user_headers}
    if method == "POST":
        request_options["json"] = {"skill": "SQL"}

    response = authenticated_client.request(method, url, **request_options)

    assert response.status_code == 404

    # Başkasının isteği mevcut bağlantıları değiştirmemeli.
    owner_response = authenticated_client.get(url)
    assert owner_response.status_code == 200
    assert owner_response.json() == [attached.json()]


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_opportunity_skills_without_token_returns_401(
    authenticated_client,
    owned_opportunity,
    method,
):
    url = f"/opportunities/{owned_opportunity['id']}/skills"

    # Yalnızca bu testin istemcisinden token'ı kaldırıyoruz.
    authenticated_client.headers.pop("Authorization", None)

    request_options = {}
    if method == "POST":
        request_options["json"] = {"skill": "Python"}

    response = authenticated_client.request(method, url, **request_options)

    assert response.status_code == 401
    
@pytest.fixture
def owned_contact(authenticated_client, owned_opportunity):
    response = authenticated_client.post(
        "/contacts",
        json={
            "name": "Private Contact",
            "role": "Recruiter",
            "email": "recruiter@example.com",
            "linkedin": "https://linkedin.com/in/example",
            "opportunity_id": owned_opportunity["id"],
        },
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_other_user_cannot_access_contact(
    authenticated_client,
    owned_contact,
    other_user_headers,
    method,
):
    url = f"/contacts/{owned_contact['id']}"
    options = {"headers": other_user_headers}

    if method == "PATCH":
        options["json"] = {"name": "Unauthorized change"}

    response = authenticated_client.request(method, url, **options)
    assert response.status_code == 404

    owner_response = authenticated_client.get(url)
    assert owner_response.status_code == 200
    assert owner_response.json() == owned_contact


def test_contact_list_contains_only_own_contacts(
    authenticated_client,
    owned_contact,
    other_user_headers,
):
    owner_response = authenticated_client.get("/contacts")
    assert owner_response.status_code == 200
    assert owner_response.json() == [owned_contact]

    other_response = authenticated_client.get(
        "/contacts",
        headers=other_user_headers,
    )
    assert other_response.status_code == 200
    assert other_response.json() == []


def test_cannot_create_contact_for_another_users_opportunity(
    authenticated_client,
    owned_contact,
    other_user_headers,
):
    payload = {
        key: value
        for key, value in owned_contact.items()
        if key != "id"
    }

    response = authenticated_client.post(
        "/contacts",
        json=payload,
        headers=other_user_headers,
    )
    assert response.status_code == 404

    # Başarısız istek yeni bir kişi oluşturmamalı.
    owner_list = authenticated_client.get("/contacts")
    assert owner_list.status_code == 200
    assert owner_list.json() == [owned_contact]

    other_list = authenticated_client.get(
        "/contacts",
        headers=other_user_headers,
    )
    assert other_list.status_code == 200
    assert other_list.json() == []


def test_cannot_move_contact_to_another_users_opportunity(
    authenticated_client,
    owned_contact,
    owned_opportunity,
    other_user_headers,
):
    payload = {
        key: value
        for key, value in owned_opportunity.items()
        if key != "id"
    }
    other_opportunity = authenticated_client.post(
        "/opportunities",
        json=payload,
        headers=other_user_headers,
    )
    assert other_opportunity.status_code == 200

    url = f"/contacts/{owned_contact['id']}"
    response = authenticated_client.patch(
        url,
        json={
            "name": "Should not change",
            "opportunity_id": other_opportunity.json()["id"],
        },
    )
    assert response.status_code == 404

    unchanged = authenticated_client.get(url)
    assert unchanged.status_code == 200
    assert unchanged.json() == owned_contact


def test_contact_opportunity_cannot_be_set_to_null(
    authenticated_client,
    owned_contact,
):
    url = f"/contacts/{owned_contact['id']}"
    response = authenticated_client.patch(
        url,
        json={"opportunity_id": None},
    )
    assert response.status_code == 422

    unchanged = authenticated_client.get(url)
    assert unchanged.status_code == 200
    assert unchanged.json() == owned_contact


def test_contacts_without_token_returns_401(client):
    response = client.get("/contacts")
    assert response.status_code == 401
    
@pytest.fixture
def owned_task(authenticated_client, owned_opportunity):
    response = authenticated_client.post(
        "/tasks",
        json={
            "opportunity_id": owned_opportunity["id"],
            "description": "Private task",
            "due_date": "2026-10-20",
            "is_completed": False,
        },
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_other_user_cannot_access_task(
    authenticated_client,
    owned_task,
    other_user_headers,
    method,
):
    url = f"/tasks/{owned_task['id']}"
    options = {"headers": other_user_headers}

    if method == "PATCH":
        options["json"] = {"is_completed": True}

    response = authenticated_client.request(method, url, **options)
    assert response.status_code == 404

    owner_response = authenticated_client.get(url)
    assert owner_response.status_code == 200
    assert owner_response.json() == owned_task


def test_task_list_contains_only_own_tasks(
    authenticated_client,
    owned_task,
    other_user_headers,
):
    owner_response = authenticated_client.get("/tasks")
    assert owner_response.status_code == 200
    assert owner_response.json() == [owned_task]

    other_response = authenticated_client.get(
        "/tasks",
        headers=other_user_headers,
    )
    assert other_response.status_code == 200
    assert other_response.json() == []


def test_cannot_create_task_for_another_users_opportunity(
    authenticated_client,
    owned_task,
    other_user_headers,
):
    payload = {
        key: value
        for key, value in owned_task.items()
        if key != "id"
    }

    response = authenticated_client.post(
        "/tasks",
        json=payload,
        headers=other_user_headers,
    )
    assert response.status_code == 404

    owner_list = authenticated_client.get("/tasks")
    assert owner_list.status_code == 200
    assert owner_list.json() == [owned_task]

    other_list = authenticated_client.get(
        "/tasks",
        headers=other_user_headers,
    )
    assert other_list.status_code == 200
    assert other_list.json() == []


def test_cannot_move_task_to_another_users_opportunity(
    authenticated_client,
    owned_task,
    owned_opportunity,
    other_user_headers,
):
    payload = {
        key: value
        for key, value in owned_opportunity.items()
        if key != "id"
    }
    other_opportunity = authenticated_client.post(
        "/opportunities",
        json=payload,
        headers=other_user_headers,
    )
    assert other_opportunity.status_code == 200

    url = f"/tasks/{owned_task['id']}"
    response = authenticated_client.patch(
        url,
        json={
            "is_completed": True,
            "opportunity_id": other_opportunity.json()["id"],
        },
    )
    assert response.status_code == 404

    unchanged = authenticated_client.get(url)
    assert unchanged.status_code == 200
    assert unchanged.json() == owned_task


def test_task_opportunity_cannot_be_set_to_null(
    authenticated_client,
    owned_task,
):
    url = f"/tasks/{owned_task['id']}"
    response = authenticated_client.patch(
        url,
        json={"opportunity_id": None},
    )
    assert response.status_code == 422

    unchanged = authenticated_client.get(url)
    assert unchanged.status_code == 200
    assert unchanged.json() == owned_task


def test_tasks_without_token_returns_401(client):
    response = client.get("/tasks")
    assert response.status_code == 401
    
@pytest.fixture
def owned_activity(authenticated_client, owned_contact):
    response = authenticated_client.post(
        "/activities",
        json={
            "opportunity_id": owned_contact["opportunity_id"],
            "contact_id": owned_contact["id"],
            "activity_type": "Telefon görüşmesi",
            "dates": "2026-10-14",
            "notes": "Private activity",
        },
    )
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def foreign_activity_links(
    authenticated_client,
    owned_opportunity,
    owned_contact,
    other_user_headers,
):
    opportunity_payload = {
        key: value
        for key, value in owned_opportunity.items()
        if key != "id"
    }
    opportunity = authenticated_client.post(
        "/opportunities",
        json=opportunity_payload,
        headers=other_user_headers,
    )
    assert opportunity.status_code == 200

    contact_payload = {
        key: value
        for key, value in owned_contact.items()
        if key != "id"
    }
    contact_payload["opportunity_id"] = opportunity.json()["id"]

    contact = authenticated_client.post(
        "/contacts",
        json=contact_payload,
        headers=other_user_headers,
    )
    assert contact.status_code == 200

    return {
        "opportunity_id": opportunity.json()["id"],
        "contact_id": contact.json()["id"],
    }


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_other_user_cannot_access_activity(
    authenticated_client,
    owned_activity,
    other_user_headers,
    method,
):
    url = f"/activities/{owned_activity['id']}"
    options = {"headers": other_user_headers}

    if method == "PATCH":
        options["json"] = {"notes": "Unauthorized change"}

    response = authenticated_client.request(method, url, **options)
    assert response.status_code == 404

    unchanged = authenticated_client.get(url)
    assert unchanged.status_code == 200
    assert unchanged.json() == owned_activity


def test_activity_list_contains_only_own_activities(
    authenticated_client,
    owned_activity,
    other_user_headers,
):
    owner_response = authenticated_client.get("/activities")
    assert owner_response.status_code == 200
    assert owner_response.json() == [owned_activity]

    other_response = authenticated_client.get(
        "/activities",
        headers=other_user_headers,
    )
    assert other_response.status_code == 200
    assert other_response.json() == []


@pytest.mark.parametrize("method", ["POST", "PATCH"])
@pytest.mark.parametrize("field", ["opportunity_id", "contact_id"])
def test_activity_cannot_use_another_users_links(
    authenticated_client,
    owned_activity,
    foreign_activity_links,
    method,
    field,
):
    payload = {
        key: value
        for key, value in owned_activity.items()
        if key != "id"
    }
    payload[field] = foreign_activity_links[field]
    payload["notes"] = "Should not be saved"

    detail_url = f"/activities/{owned_activity['id']}"
    url = "/activities" if method == "POST" else detail_url

    response = authenticated_client.request(method, url, json=payload)
    assert response.status_code == 404

    listed = authenticated_client.get("/activities")
    assert listed.status_code == 200
    assert listed.json() == [owned_activity]


@pytest.mark.parametrize("method", ["POST", "PATCH"])
def test_activity_rejects_contact_from_different_owned_opportunity(
    authenticated_client,
    owned_activity,
    owned_opportunity,
    method,
):
    opportunity_payload = {
        key: value
        for key, value in owned_opportunity.items()
        if key != "id"
    }
    second_opportunity = authenticated_client.post(
        "/opportunities",
        json=opportunity_payload,
    )
    assert second_opportunity.status_code == 200

    # Mevcut kişi eski fırsata bağlı; yeni fırsatla eşleşmiyor.
    payload = {
        "opportunity_id": second_opportunity.json()["id"],
        "notes": "Should not be saved",
    }
    if method == "POST":
        payload = {
            **{
                key: value
                for key, value in owned_activity.items()
                if key != "id"
            },
            **payload,
        }

    detail_url = f"/activities/{owned_activity['id']}"
    url = "/activities" if method == "POST" else detail_url

    response = authenticated_client.request(method, url, json=payload)
    assert response.status_code == 422

    listed = authenticated_client.get("/activities")
    assert listed.status_code == 200
    assert listed.json() == [owned_activity]


def test_activity_can_move_when_contact_is_explicitly_removed(
    authenticated_client,
    owned_activity,
    owned_opportunity,
):
    payload = {
        key: value
        for key, value in owned_opportunity.items()
        if key != "id"
    }
    second_opportunity = authenticated_client.post(
        "/opportunities",
        json=payload,
    )
    assert second_opportunity.status_code == 200

    url = f"/activities/{owned_activity['id']}"
    response = authenticated_client.patch(
        url,
        json={
            "opportunity_id": second_opportunity.json()["id"],
            "contact_id": None,
        },
    )
    assert response.status_code == 200

    persisted = authenticated_client.get(url)
    assert persisted.status_code == 200
    assert persisted.json() == {
        **owned_activity,
        "opportunity_id": second_opportunity.json()["id"],
        "contact_id": None,
    }


def test_activity_opportunity_cannot_be_set_to_null(
    authenticated_client,
    owned_activity,
):
    url = f"/activities/{owned_activity['id']}"
    response = authenticated_client.patch(
        url,
        json={"opportunity_id": None},
    )
    assert response.status_code == 422

    unchanged = authenticated_client.get(url)
    assert unchanged.status_code == 200
    assert unchanged.json() == owned_activity


def test_activities_without_token_returns_401(client):
    response = client.get("/activities")
    assert response.status_code == 401
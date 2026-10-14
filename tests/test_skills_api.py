def _create_skill(client, name, category=None):
    return client.post(
        "/skills",
        json={"name": name, "category": category},
    )


def _create_opportunity(client):
    payload = {
        "company": "Test Şirketi",
        "position": "Test Pozisyon",
        "type": "staj",
        "application_date": "2026-09-04",
        "job_link": "https://example.com",
        "salary": 10000,
        "location": "İstanbul",
        "status": "Başvuruldu",
        "notes": "Test notu",
        "next_action": "Takip et",
        "last_contact_date": "2026-09-04",
    }

    response = client.post("/opportunities", json=payload)

    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_create_skill_returns_201_with_id(authenticated_client):
    client = authenticated_client
    response = _create_skill(client, "Python", "language")

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["name"] == "Python"
    assert body["category"] == "language"


def test_create_duplicate_skill_returns_409(authenticated_client):
    client = authenticated_client
    assert _create_skill(client, "Python").status_code == 201

    response = _create_skill(client, "Python")

    assert response.status_code == 409


def test_create_skill_with_different_case_and_spaces_returns_409(
    authenticated_client,
):
    client = authenticated_client
    assert _create_skill(client, "Python").status_code == 201

    response = _create_skill(client, "  PYTHON  ")

    assert response.status_code == 409


def test_create_skill_with_blank_name_returns_422(authenticated_client):
    client = authenticated_client
    response = _create_skill(client, "   ")

    assert response.status_code == 422


def test_create_skill_without_name_returns_422(authenticated_client):
    client = authenticated_client
    response = client.post("/skills", json={})

    assert response.status_code == 422


def test_resolve_skill_finds_existing_skill(authenticated_client):
    client = authenticated_client
    assert _create_skill(client, "Python", "language").status_code == 201

    response = client.get("/skills/resolve", params={"name": "python"})

    assert response.status_code == 200
    assert response.json()["name"] == "Python"


def test_resolve_unknown_skill_returns_404(client):
    response = client.get(
        "/skills/resolve",
        params={"name": "no-such-skill"},
    )

    assert response.status_code == 404


def test_turkish_dotless_i_matches_existing_skill(authenticated_client):
    client = authenticated_client
    assert _create_skill(client, "FastAPI", "framework").status_code == 201

    # Noktasız ı ile yazılan ad da aynı beceriyi bulmalı.
    response = _create_skill(client, "Fastap\u0131")

    assert response.status_code == 409


def test_add_alias_makes_skill_resolvable(authenticated_client):
    client = authenticated_client
    created = _create_skill(client, "PostgreSQL", "database")
    assert created.status_code == 201
    skill_id = created.json()["id"]

    response = client.post(
        f"/skills/{skill_id}/aliases",
        json={"alias": "Postgres"},
    )

    assert response.status_code == 201

    resolved = client.get("/skills/resolve", params={"name": "POSTGRES"})
    assert resolved.status_code == 200
    assert resolved.json()["name"] == "PostgreSQL"


def test_add_duplicate_alias_returns_409(authenticated_client):
    client = authenticated_client
    created = _create_skill(client, "PostgreSQL")
    assert created.status_code == 201
    skill_id = created.json()["id"]

    first_alias = client.post(
        f"/skills/{skill_id}/aliases",
        json={"alias": "postgres"},
    )
    assert first_alias.status_code == 201

    response = client.post(
        f"/skills/{skill_id}/aliases",
        json={"alias": "  Postgres "},
    )

    assert response.status_code == 409


def test_add_alias_to_unknown_skill_returns_404(authenticated_client):
    client = authenticated_client
    response = client.post(
        "/skills/9999/aliases",
        json={"alias": "x"},
    )

    assert response.status_code == 404


def test_add_blank_alias_returns_422(authenticated_client):
    client = authenticated_client
    created = _create_skill(client, "PostgreSQL")
    assert created.status_code == 201
    skill_id = created.json()["id"]

    response = client.post(
        f"/skills/{skill_id}/aliases",
        json={"alias": "   "},
    )

    assert response.status_code == 422


def test_attach_skill_to_opportunity_via_alias(authenticated_client):
    client = authenticated_client
    created = _create_skill(client, "PostgreSQL", "database")
    assert created.status_code == 201
    skill_id = created.json()["id"]

    alias = client.post(
        f"/skills/{skill_id}/aliases",
        json={"alias": "postgres"},
    )
    assert alias.status_code == 201

    opportunity_id = _create_opportunity(client)
    url = f"/opportunities/{opportunity_id}/skills"

    response = client.post(url, json={"skill": "POSTGRES"})

    assert response.status_code == 201

    listed = client.get(url)
    assert listed.status_code == 200
    assert [skill["name"] for skill in listed.json()] == ["PostgreSQL"]


def test_attach_same_skill_twice_returns_409(authenticated_client):
    client = authenticated_client
    assert _create_skill(client, "Python", "language").status_code == 201

    opportunity_id = _create_opportunity(client)
    url = f"/opportunities/{opportunity_id}/skills"
    assert client.post(url, json={"skill": "python"}).status_code == 201

    response = client.post(url, json={"skill": "Python"})

    assert response.status_code == 409


def test_attach_unknown_skill_returns_404(authenticated_client):
    client = authenticated_client
    opportunity_id = _create_opportunity(client)

    response = client.post(
        f"/opportunities/{opportunity_id}/skills",
        json={"skill": "no-such-skill"},
    )

    assert response.status_code == 404


def test_attach_skill_to_unknown_opportunity_returns_404(
    authenticated_client,
):
    client = authenticated_client
    assert _create_skill(client, "Python", "language").status_code == 201

    response = client.post(
        "/opportunities/9999/skills",
        json={"skill": "python"},
    )

    assert response.status_code == 404


def test_create_skill_without_token_returns_401(client):
    response = client.post(
        "/skills",
        json={"name": "Python", "category": "language"},
    )

    assert response.status_code == 401


def test_add_alias_without_token_returns_401(client):
    response = client.post(
        "/skills/9999/aliases",
        json={"alias": "postgres"},
    )

    assert response.status_code == 401
def _create_skill(client, name, category=None):
    return client.post("/skills", json={"name": name, "category": category})


def test_create_skill_returns_201_with_id(client):
    response = _create_skill(client, "Python", "language")

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["name"] == "Python"
    assert body["category"] == "language"


def test_create_duplicate_skill_returns_409(client):
    assert _create_skill(client, "Python").status_code == 201

    response = _create_skill(client, "Python")

    assert response.status_code == 409


def test_create_skill_with_different_case_and_spaces_returns_409(client):
    assert _create_skill(client, "Python").status_code == 201

    response = _create_skill(client, "  PYTHON  ")

    assert response.status_code == 409


def test_create_skill_with_blank_name_returns_422(client):
    response = _create_skill(client, "   ")

    assert response.status_code == 422


def test_create_skill_without_name_returns_422(client):
    response = client.post("/skills", json={})

    assert response.status_code == 422


def test_resolve_skill_finds_existing_skill(client):
    assert _create_skill(client, "Python", "language").status_code == 201

    response = client.get("/skills/resolve", params={"name": "python"})

    assert response.status_code == 200
    assert response.json()["name"] == "Python"


def test_resolve_unknown_skill_returns_404(client):
    response = client.get("/skills/resolve", params={"name": "no-such-skill"})

    assert response.status_code == 404


def test_turkish_dotless_i_matches_existing_skill(client):
    assert _create_skill(client, "FastAPI", "framework").status_code == 201

    # "Fastap\u0131" = "Fastapı" (noktasız ı), klavye hatasını taklit eder
    response = _create_skill(client, "Fastap\u0131")

    assert response.status_code == 409
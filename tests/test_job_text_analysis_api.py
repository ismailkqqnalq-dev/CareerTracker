import time

from app.models.skills import SkillSuggestion
from app.services.job_text_analysis_service import analyze_job_text


def _add_private_skill(client, name, category):
    response = client.post(
        "/skills",
        json={"name": name, "category": category},
    )
    assert response.status_code == 201
    return response.json()


def test_analyze_text_finds_visible_skills_and_conservative_sections(authenticated_client):
    client = authenticated_client
    python_skill = _add_private_skill(client, "Python", "language")
    fastapi_skill = _add_private_skill(client, "FastAPI", "framework")
    postgres_skill = _add_private_skill(client, "PostgreSQL", "database")

    response = client.post(
        "/job-analysis",
        json={
            "text": (
                "Pozisyon: Backend Engineer\n"
                "Aranan Nitelikler:\n"
                "Python ve FastAPI bilgisi\n"
                "Tercihen:\n"
                "PostgreSQL deneyimi"
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["role"] == "Backend Engineer"
    skills = {skill["name"]: skill for skill in payload["skills"]}
    assert set(skills) == {"Python", "FastAPI", "PostgreSQL"}
    assert skills["Python"]["skill_id"] == python_skill["id"]
    assert skills["FastAPI"]["skill_id"] == fastapi_skill["id"]
    assert skills["PostgreSQL"]["skill_id"] == postgres_skill["id"]
    assert skills["Python"]["occurrences"][0]["section"] == "required"
    assert skills["FastAPI"]["occurrences"][0]["section"] == "required"
    assert skills["PostgreSQL"]["occurrences"][0]["section"] == "preferred"


def test_analyzer_handles_symbolic_names_and_avoids_bare_short_matches(authenticated_client):
    client = authenticated_client
    _add_private_skill(client, "C", "language")
    _add_private_skill(client, "C#", "language")
    _add_private_skill(client, "C++", "language")
    _add_private_skill(client, "R", "language")

    response = client.post(
        "/job-analysis",
        json={"text": "C# programming experience and C++\nR programlama dili deneyimi tercih sebebidir.\nR notu; Python programming experience."},
    )

    assert response.status_code == 200
    skills = {skill["name"]: skill for skill in response.json()["skills"]}
    assert set(skills) == {"C#", "C++", "R"}
    assert len(skills["R"]["occurrences"]) == 1
    assert skills["R"]["occurrences"][0]["matched_text"] == "R"


def test_analyzer_does_not_expose_another_users_private_skill(authenticated_client):
    owner = authenticated_client
    private_skill = _add_private_skill(owner, "OwnerOnlyTool", "tool")
    registration = owner.post(
        "/auth/register",
        json={"email": "second@example.com", "password": "StrongPass456"},
    )
    assert registration.status_code == 201
    login = owner.post(
        "/auth/token",
        data={"username": "second@example.com", "password": "StrongPass456"},
    )
    assert login.status_code == 200

    from fastapi.testclient import TestClient
    from app.main import app

    other_user = TestClient(app)
    other_user.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    response = other_user.post(
        "/job-analysis",
        json={"text": "We need experience with OwnerOnlyTool."},
    )

    assert response.status_code == 200
    assert all(skill["skill_id"] != private_skill["id"] for skill in response.json()["skills"])


def test_analyzer_requires_authentication():
    from fastapi.testclient import TestClient
    from app.main import app

    response = TestClient(app).post("/job-analysis", json={"text": "Python"})

    assert response.status_code == 401


def test_analyzer_rejects_empty_and_oversized_text(authenticated_client):
    client = authenticated_client

    empty = client.post("/job-analysis", json={"text": " \n "})
    oversized = client.post("/job-analysis", json={"text": "x" * 100_001})

    assert empty.status_code == 422
    assert empty.json()["error_code"] == "empty_job_text"
    assert oversized.status_code == 413
    assert oversized.json()["error_code"] == "job_text_too_large"


def test_analyzing_text_does_not_create_persistent_rows(authenticated_client, db_session):
    client = authenticated_client
    _add_private_skill(client, "Python", "language")
    before_suggestions = db_session.query(SkillSuggestion).count()

    response = client.post("/job-analysis", json={"text": "Python"})

    assert response.status_code == 200
    assert db_session.query(SkillSuggestion).count() == before_suggestions


def test_job_analysis_handles_100kb_adversarial_text_quickly(db_session):
    cases = [
        "requirements" + " " * 99_980 + "x",
        "role: a" + " " * 99_990 + "x",
        "x" * 100_000,
        ("requirements: x\n" * 6_000)[:100_000],
        ("Requirements:\nPreferred:\n" * 4_000)[:100_000],
    ]

    started = time.perf_counter()
    for text in cases:
        analyze_job_text(db_session, user_id=1, text=text)

    assert time.perf_counter() - started < 1.0

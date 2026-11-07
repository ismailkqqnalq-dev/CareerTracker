from app.models.skills import Skill, SkillSuggestion, UserSkill
from app.models.users import User


def _add_private_skill(client, name, category):
    response = client.post("/skills", json={"name": name, "category": category})
    assert response.status_code == 201
    return response.json()


def test_analyzer_extracts_explicit_posting_fields_and_source_lines(authenticated_client):
    client = authenticated_client
    response = client.post(
        "/job-analysis",
        json={
            "text": (
                "Şirket: Örnek Teknoloji\n"
                "İş Unvanı: Senior Backend Engineer\n"
                "Konum: İstanbul\n"
                "İstihdam Türü: Tam zamanlı\n"
                "Çalışma Modeli: Hibrit\n"
                "Maaş Aralığı: ₺100.000–₺120.000\n"
                "Deneyim: 5+ yıl\n"
                "Eğitim Düzeyi: Lisans\n"
                "Başvuru Linki: https://example.com/jobs/backend\n"
                "Aranan Nitelikler:\nPython"
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "Senior Backend Engineer"
    assert body["role_line_number"] == 2
    assert body["metadata"] == {
        "company": {"value": "Örnek Teknoloji", "line_number": 1},
        "location": {"value": "İstanbul", "line_number": 3},
        "employment_type": {"value": "Tam zamanlı", "line_number": 4},
        "work_arrangement": {"value": "Hibrit", "line_number": 5},
        "salary": {"value": "₺100.000–₺120.000", "line_number": 6},
        "experience": {"value": "5+ yıl", "line_number": 7},
        "education": {"value": "Lisans", "line_number": 8},
        "application_url": {
            "value": "https://example.com/jobs/backend",
            "line_number": 9,
        },
    }


def test_analyzer_keeps_legacy_dash_separated_role_labels(authenticated_client):
    response = authenticated_client.post(
        "/job-analysis",
        json={"text": "Position - Data Engineer"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "Data Engineer"
    assert response.json()["role_line_number"] == 1


def test_analyzer_compares_required_preferred_and_unspecified_skills_to_profile(
    authenticated_client,
):
    client = authenticated_client
    python = _add_private_skill(client, "Python", "language")
    fastapi = _add_private_skill(client, "FastAPI", "framework")
    postgres = _add_private_skill(client, "PostgreSQL", "database")
    kubernetes = _add_private_skill(client, "Kubernetes", "tool")
    docker = _add_private_skill(client, "Docker", "tool")

    for skill, level, years in (
        (python, "advanced", 3.5),
        (postgres, "intermediate", 2),
    ):
        added = client.post(
            "/users/me/skills",
            json={
                "skill_id": skill["id"],
                "proficiency_level": level,
                "years_experience": years,
            },
        )
        assert added.status_code == 201

    response = client.post(
        "/job-analysis",
        json={
            "text": (
                "Required Skills:\nPython, FastAPI, PostgreSQL\n"
                "Preferred Skills:\nKubernetes\n"
                "Other Tools:\nDocker"
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["profile_match"] == {
        "required": {
            "total_count": 3,
            "matched_count": 2,
            "match_percentage": 66.67,
            "missing_skills": ["FastAPI"],
        },
        "preferred": {
            "total_count": 1,
            "matched_count": 0,
            "match_percentage": 0.0,
            "missing_skills": ["Kubernetes"],
        },
        "unspecified": {
            "total_count": 1,
            "matched_count": 0,
            "match_percentage": 0.0,
            "missing_skills": ["Docker"],
        },
    }
    skills = {item["name"]: item for item in body["skills"]}
    assert skills["Python"]["profile_status"] == "in_profile"
    assert skills["Python"]["profile_proficiency_level"] == "advanced"
    assert skills["Python"]["profile_years_experience"] == 3.5
    assert skills["FastAPI"]["profile_status"] == "missing"
    assert skills["FastAPI"]["profile_proficiency_level"] is None
    assert skills["PostgreSQL"]["profile_proficiency_level"] == "intermediate"
    assert all(
        item["profile_status"] in {"in_profile", "missing"}
        for item in body["skills"]
    )


def test_analyzer_classifies_ideally_also_as_preferred_for_profile_match(
    authenticated_client,
):
    client = authenticated_client
    python = _add_private_skill(client, "Python", "language")
    _add_private_skill(client, "FastAPI", "framework")
    added = client.post("/users/me/skills", json={"skill_id": python["id"]})
    assert added.status_code == 201

    response = client.post(
        "/job-analysis",
        json={
            "text": (
                "Minimum Qualifications:\nFastAPI\n"
                "Ideally, you also:\nPython"
            )
        },
    )

    assert response.status_code == 200
    match = response.json()["profile_match"]
    assert match["required"] == {
        "total_count": 1,
        "matched_count": 0,
        "match_percentage": 0.0,
        "missing_skills": ["FastAPI"],
    }
    assert match["preferred"] == {
        "total_count": 1,
        "matched_count": 1,
        "match_percentage": 100.0,
        "missing_skills": [],
    }
    assert match["unspecified"]["total_count"] == 0


def test_analyzer_does_not_guess_unlabeled_job_details_or_store_them(
    authenticated_client, db_session
):
    client = authenticated_client
    response = client.post(
        "/job-analysis",
        json={"text": "Remote role at Example. Salary is competitive.\nPython"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["role"] is None
    assert body["role_line_number"] is None
    assert all(value is None for value in body["metadata"].values())
    assert body["profile_match"]["required"]["match_percentage"] is None
    assert db_session.query(SkillSuggestion).count() == 0


def test_analyzer_compares_a_shared_skill_only_with_the_calling_users_profile(
    authenticated_client, db_session
):
    owner = db_session.query(User).filter_by(email="owner@example.com").one()
    shared_skill = Skill(name="SharedProfileIsolation", category="tool")
    db_session.add(shared_skill)
    db_session.flush()
    db_session.add(
        UserSkill(
            user_id=owner.id,
            skill_id=shared_skill.id,
            proficiency_level="expert",
            years_experience=12,
        )
    )
    db_session.commit()

    authenticated_client.post(
        "/auth/register",
        json={"email": "profile-reader@example.com", "password": "StrongPass456"},
    )
    login = authenticated_client.post(
        "/auth/token",
        data={"username": "profile-reader@example.com", "password": "StrongPass456"},
    )
    assert login.status_code == 200

    from fastapi.testclient import TestClient
    from app.main import app

    other_user = TestClient(app)
    other_user.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    response = other_user.post(
        "/job-analysis",
        json={"text": "Required Skills:\nSharedProfileIsolation"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["skills"][0]["profile_status"] == "missing"
    assert body["skills"][0]["profile_proficiency_level"] is None
    assert body["skills"][0]["profile_years_experience"] is None
    assert body["profile_match"]["required"]["match_percentage"] == 0.0

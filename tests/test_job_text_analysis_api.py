import time

import pytest

from app.models.skills import PersonalSkillAlias, SkillSuggestion
from app.services.job_text_analysis_service import (
    _fold_for_matching,
    _line_section,
    analyze_job_text,
)


def _add_private_skill(client, name, category):
    response = client.post(
        "/skills",
        json={"name": name, "category": category},
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.parametrize(
    ("heading", "expected_section"),
    [
        ("Skills Required:", "required"),
        ("Qualifications:", "required"),
        ("Basic Qualifications:", "required"),
        ("Minimum Requirements:", "required"),
        ("Minimum Qualifications:", "required"),
        ("What you'll need to be successful", "required"),
        ("Essential Skills:", "required"),
        ("What You Bring:", "required"),
        ("What We're Looking For:", "required"),
        ("Gerekli Yetkinlikler:", "required"),
        ("Aranan Yetkinlikler:", "required"),
        ("Temel Nitelikler:", "required"),
        ("İstenen Yetkinlikler:", "required"),
        ("Desired Qualifications:", "preferred"),
        ("Desirable Skills:", "preferred"),
        ("Good to Have:", "preferred"),
        ("Nice-to-haves:", "preferred"),
        ("A Plus:", "preferred"),
        ("Preferred Experience:", "preferred"),
        ("Any of the following would be a bonus", "preferred"),
        ("Any of the following would be a bonus.", "preferred"),
        ("The Essentials", "required"),
        ("To Be Successful, You'll Need", "required"),
        ("Bonus Points If You Have", "preferred"),
        ("Bonus Points For", "preferred"),
        ("Tercih Edilen Yetkinlikler:", "preferred"),
        ("Artı Sayılan Özellikler:", "preferred"),
    ],
)
def test_common_job_ad_headings_classify_requirement_sections(
    heading, expected_section
):
    assert _line_section(heading, "unspecified") == (expected_section, True)


@pytest.mark.parametrize(
    "heading",
    [
        "Tech Stack",
        "Our Tech Stack",
        "What You'll Do",
        "Some Things You Might Work On",
        "The Role",
        "The Rewards Package",
    ],
)
@pytest.mark.parametrize("current_section", ["required", "preferred"])
def test_non_requirement_headings_reset_section_classification(
    heading, current_section
):
    assert _line_section(heading, current_section) == ("unspecified", True)


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
    assert payload["role_source"] == "explicit"
    skills = {skill["name"]: skill for skill in payload["skills"]}
    assert set(skills) == {"Python", "FastAPI", "PostgreSQL"}
    assert skills["Python"]["skill_id"] == python_skill["id"]
    assert skills["FastAPI"]["skill_id"] == fastapi_skill["id"]
    assert skills["PostgreSQL"]["skill_id"] == postgres_skill["id"]
    assert skills["Python"]["occurrences"][0]["section"] == "required"
    assert skills["FastAPI"]["occurrences"][0]["section"] == "required"
    assert skills["PostgreSQL"]["occurrences"][0]["section"] == "preferred"


def test_analyzer_uses_job_title_headline_when_no_role_label(db_session):
    result = analyze_job_text(
        db_session,
        user_id=1,
        text="Senior Software Engineer (Java or Python)\nRemote\nWe build tools for teams.",
    )

    assert result["role"] == "Senior Software Engineer (Java or Python)"
    assert result["role_line_number"] == 1
    assert result["role_source"] == "headline"


def test_explicit_role_label_takes_precedence_over_headline(db_session):
    result = analyze_job_text(
        db_session,
        user_id=1,
        text="Senior Software Engineer\nPosition: Backend Engineer",
    )

    assert result["role"] == "Backend Engineer"
    assert result["role_line_number"] == 2
    assert result["role_source"] == "explicit"


def test_analyzer_does_not_treat_introductory_prose_as_a_job_title(db_session):
    result = analyze_job_text(
        db_session,
        user_id=1,
        text="We are looking for a software engineer to join our team.\nPython",
    )

    assert result["role"] is None


def test_analyzer_does_not_infer_a_role_from_a_later_body_line(db_session):
    result = analyze_job_text(
        db_session,
        user_id=1,
        text="About us\nFirst intro\nSecond intro\nThird intro\nFourth intro\nSenior Data Engineer",
    )

    assert result["role"] is None


@pytest.mark.parametrize(
    "headline",
    [
        "Backend Engineer — Data Platform",
        "Lead Data Engineer - Databricks",
        "Senior Backend Software Engineer - Python",
    ],
)
def test_analyzer_recognizes_public_job_titles_with_specialization_suffixes(
    db_session, headline
):
    result = analyze_job_text(db_session, user_id=1, text=headline)

    assert result["role"] == headline
    assert result["role_line_number"] == 1
    assert result["role_source"] == "headline"


def test_analyzer_handles_symbolic_names_and_avoids_bare_short_matches(authenticated_client):
    client = authenticated_client
    _add_private_skill(client, "C", "language")
    _add_private_skill(client, "C#", "language")
    _add_private_skill(client, "C++", "language")
    _add_private_skill(client, "R", "language")
    _add_private_skill(client, "Go", "language")

    response = client.post(
        "/job-analysis",
        json={"text": "C# programming experience and C++\nR programlama dili deneyimi tercih sebebidir.\nR notu; Go programming experience.\nGo board games."},
    )

    assert response.status_code == 200
    skills = {skill["name"]: skill for skill in response.json()["skills"]}
    assert set(skills) == {"C#", "C++", "R", "Go"}
    assert len(skills["R"]["occurrences"]) == 1
    assert skills["R"]["occurrences"][0]["matched_text"] == "R"
    assert [item["matched_text"] for item in skills["Go"]["occurrences"]] == ["Go"]


def test_analyzer_classifies_observed_frontend_job_section_labels(authenticated_client):
    client = authenticated_client
    _add_private_skill(client, "React", "framework")
    _add_private_skill(client, "TypeScript", "language")
    _add_private_skill(client, "Playwright", "testing")

    response = client.post(
        "/job-analysis",
        json={
            "text": (
                "Frontend Engineer\n"
                "The Essentials:\nReact\n"
                "To Be Successful, You'll Need:\nTypeScript\n"
                "Bonus Points If You Have:\nPlaywright"
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    skills = {skill["name"]: skill for skill in payload["skills"]}
    assert payload["role"] == "Frontend Engineer"
    assert skills["React"]["occurrences"][0]["section"] == "required"
    assert skills["TypeScript"]["occurrences"][0]["section"] == "required"
    assert skills["Playwright"]["occurrences"][0]["section"] == "preferred"


def test_analyzer_resets_section_after_observed_tech_stack_heading(authenticated_client):
    client = authenticated_client
    _add_private_skill(client, "Python", "language")
    _add_private_skill(client, "Next.js", "framework")

    response = client.post(
        "/job-analysis",
        json={
            "text": (
                "Backend Engineer\n"
                "Qualifications:\nPython\n"
                "Tech Stack\nNext.js"
            )
        },
    )

    assert response.status_code == 200
    skills = {skill["name"]: skill for skill in response.json()["skills"]}
    assert skills["Python"]["occurrences"][0]["section"] == "required"
    assert skills["Next.js"]["occurrences"][0]["section"] == "unspecified"


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


def test_analyzer_matches_turkish_aliases_and_ascii_ocr_spelling(authenticated_client):
    client = authenticated_client
    _add_private_skill(client, "Bilgisayarlı Görü", "tool")
    _add_private_skill(client, "Çağrı Şöğüt", "tool")

    response = client.post(
        "/job-analysis",
        json={"text": "Bilgisayarlı Görü\nBilgisayarli Goru\nÇağrı Şöğüt\nCagri Sogut"},
    )

    assert response.status_code == 200
    skills = {skill["name"]: skill for skill in response.json()["skills"]}
    assert set(skills) == {"Bilgisayarlı Görü", "Çağrı Şöğüt"}
    assert [item["matched_text"] for item in skills["Bilgisayarlı Görü"]["occurrences"]] == [
        "Bilgisayarlı Görü", "Bilgisayarli Goru"
    ]
    assert [item["matched_text"] for item in skills["Çağrı Şöğüt"]["occurrences"]] == [
        "Çağrı Şöğüt", "Cagri Sogut"
    ]


def test_analyzer_does_not_choose_between_aliases_colliding_after_folding(authenticated_client):
    client = authenticated_client
    _add_private_skill(client, "Data Şcience", "tool")
    _add_private_skill(client, "Data Science", "tool")
    _add_private_skill(client, "Science", "concept")

    response = client.post("/job-analysis", json={"text": "Data Science"})

    assert response.status_code == 200
    assert response.json()["skills"] == []


def test_analyzer_resets_section_for_unknown_short_colon_heading(authenticated_client):
    client = authenticated_client
    _add_private_skill(client, "Python", "language")
    _add_private_skill(client, "FastAPI", "framework")

    response = client.post(
        "/job-analysis",
        json={"text": "Aranan Nitelikler:\nPython\nAbout us:\nFastAPI"},
    )

    assert response.status_code == 200
    skills = {skill["name"]: skill for skill in response.json()["skills"]}
    assert skills["Python"]["occurrences"][0]["section"] == "required"
    assert skills["FastAPI"]["occurrences"][0]["section"] == "unspecified"


def test_match_folding_preserves_character_offsets_and_folds_all_requested_letters():
    original = "şğçöüıİâîû"

    folded = _fold_for_matching(original)

    assert folded == "sgcouiiaiu"
    assert len(folded) == len(original)


def test_analyzer_recognizes_folded_turkish_required_and_preferred_headings(authenticated_client):
    client = authenticated_client
    _add_private_skill(client, "Python", "language")
    _add_private_skill(client, "FastAPI", "framework")

    response = client.post(
        "/job-analysis",
        json={
            "text": (
                "İş İçin Gerekli Beceriler:\nPython\n"
                "Öne Çıkan Özellikler:\nFastAPI"
            )
        },
    )

    assert response.status_code == 200
    skills = {skill["name"]: skill for skill in response.json()["skills"]}
    assert skills["Python"]["occurrences"][0]["section"] == "required"
    assert skills["FastAPI"]["occurrences"][0]["section"] == "preferred"


def test_personal_alias_is_not_visible_to_another_user(authenticated_client, db_session):
    owner = authenticated_client
    skill = _add_private_skill(owner, "OwnerLanguage", "language")
    from app.models.users import User

    owner_user = db_session.query(User).filter_by(email="owner@example.com").one()
    db_session.add(
        PersonalSkillAlias(
            user_id=owner_user.id,
            alias="ownerprivatealias",
            skill_id=skill["id"],
        )
    )
    db_session.commit()

    registration = owner.post(
        "/auth/register",
        json={"email": "alias-reader@example.com", "password": "StrongPass456"},
    )
    assert registration.status_code == 201
    login = owner.post(
        "/auth/token",
        data={"username": "alias-reader@example.com", "password": "StrongPass456"},
    )
    assert login.status_code == 200

    from fastapi.testclient import TestClient
    from app.main import app

    other_user = TestClient(app)
    other_user.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    response = other_user.post("/job-analysis", json={"text": "OwnerPrivateAlias"})

    assert response.status_code == 200
    assert response.json()["skills"] == []
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


def test_folded_heading_over_200_characters_is_not_classified():
    from app.services.job_text_analysis_service import _line_section

    long_heading = "İş İçin Gerekli Beceriler" + " " * 190 + ":"

    assert len(long_heading) > 200
    assert _line_section(long_heading, "unspecified") == ("unspecified", False)


def test_analyzer_matches_nfd_text_and_preserves_original_match(authenticated_client):
    import unicodedata

    client = authenticated_client
    _add_private_skill(client, "Café", "concept")
    decomposed = unicodedata.normalize("NFD", "Café")

    response = client.post(
        "/job-analysis",
        json={"text": f"Experience with {decomposed}."},
    )

    assert response.status_code == 200
    skills = response.json()["skills"]
    assert [skill["name"] for skill in skills] == ["Café"]
    assert skills[0]["occurrences"][0]["matched_text"] == decomposed


def test_analyzer_matches_composed_text_to_nfd_personal_alias(authenticated_client):
    import unicodedata

    client = authenticated_client
    skill = _add_private_skill(client, "Cafe Tool", "tool")
    decomposed_alias = unicodedata.normalize("NFD", "Café")
    alias_response = client.post(
        f"/skills/{skill['id']}/aliases",
        json={"alias": decomposed_alias},
    )
    assert alias_response.status_code == 201

    response = client.post("/job-analysis", json={"text": "Café"})

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["skills"]] == ["Cafe Tool"]
    assert response.json()["skills"][0]["occurrences"][0]["matched_text"] == "Café"


def test_analyzer_classifies_nfd_turkish_heading(authenticated_client):
    import unicodedata

    client = authenticated_client
    _add_private_skill(client, "Python", "language")
    heading = unicodedata.normalize("NFD", "İş İçin Gerekli Beceriler:")

    response = client.post(
        "/job-analysis",
        json={"text": f"{heading}\nPython"},
    )

    assert response.status_code == 200
    assert response.json()["skills"][0]["occurrences"][0]["section"] == "required"


def test_analyzer_treats_composed_and_nfd_aliases_as_ambiguous(authenticated_client):
    import unicodedata

    client = authenticated_client
    _add_private_skill(client, "Café", "concept")
    other_skill = _add_private_skill(client, "Coffee Tool", "tool")
    decomposed_alias = unicodedata.normalize("NFD", "Café")
    alias_response = client.post(
        f"/skills/{other_skill['id']}/aliases",
        json={"alias": decomposed_alias},
    )
    assert alias_response.status_code == 201

    response = client.post("/job-analysis", json={"text": "Café"})

    assert response.status_code == 200
    assert response.json()["skills"] == []

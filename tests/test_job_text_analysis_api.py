import time

import pytest

from app.models.skills import PersonalSkillAlias, SkillSuggestion
from app.services import job_text_analysis_service as job_analysis_service
from app.services.skill_catalog_service import seed_skill_catalog
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


def test_alias_search_work_does_not_scale_as_aliases_times_lines(
    db_session, monkeypatch
):
    seed_skill_catalog(db_session)
    original_matcher = job_analysis_service._find_alias_matches
    scanned_lines = []

    def counting_matcher(text, automaton):
        scanned_lines.append(len(text))
        return original_matcher(text, automaton)

    monkeypatch.setattr(job_analysis_service, "_find_alias_matches", counting_matcher)
    text = "\n".join(["Python, SQL and cloud experience"] * 5)
    result = analyze_job_text(db_session, user_id=1, text=text)

    assert {skill["name"] for skill in result["skills"]} >= {"Python", "SQL"}
    assert scanned_lines == [len("Python, SQL and cloud experience")] * 5


def test_alias_automaton_cache_reuses_catalog_and_has_a_fixed_bound(db_session):
    seed_skill_catalog(db_session)
    cached_builder = job_analysis_service._build_alias_automaton
    cached_builder.cache_clear()
    text = "Python, SQL and cloud experience"

    try:
        first = analyze_job_text(db_session, user_id=1, text=text)
        second = analyze_job_text(db_session, user_id=1, text=text)
        cache_info = cached_builder.cache_info()

        assert first == second
        assert cache_info.hits == 1
        assert cache_info.maxsize == 16
    finally:
        cached_builder.cache_clear()


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
        ("Technical Skills", "required"),
        ("Technical Skills & Experience", "required"),
        ("Skills & Experience", "required"),
        ("Required Skills and Experience", "required"),
        ("Required Skills and Qualifications:", "required"),
        ("Required Skills & Qualifications:", "required"),
        ("Skills and Qualifications:", "required"),
        ("Essential:", "required"),
        ("What We're Looking For (Required):", "required"),
        ("What You Have:", "required"),
        ("What It Takes:", "required"),
        ("What It Takes to Be Successful:", "required"),
        ("Have You Got What It Takes?", "required"),
        ("What We Require:", "required"),
        ("Qualifications You Will Bring:", "required"),
        ("You might be a great fit if you:", "required"),
        ("What You Will Bring With You", "required"),
        ("What We Look For", "required"),
        ("YOU MIGHT BE A FIT IF YOU HAVE:", "required"),
        ("You might be a good fit if you:", "required"),
        ("Helpful (not required)", "preferred"),
        ("What We Need From You:", "required"),
        ("What We Expect You to Know", "required"),
        ("Must-haves:", "required"),
        ("Must haves", "required"),
        ("YOU'LL BRING THESE QUALIFICATIONS:", "required"),
        ("YOU\u2019LL BRING THESE QUALIFICATIONS AS A SENIOR ENGINEER:", "required"),
        ("THESE QUALIFICATIONS WOULD BE NICE TO HAVE:", "preferred"),
        ("THESE QUALIFICATIONS WOULD BE NICE TO HAVE", "preferred"),
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
        ("Ideally, you also:", "preferred"),
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


@pytest.mark.parametrize(
    ("heading", "current_section", "expected_section"),
    [
        ("What You Will Need", "unspecified", "required"),
        ("Who We Are Looking For", "unspecified", "required"),
        ("About You", "unspecified", "required"),
        ("Who You Are:", "preferred", "unspecified"),
        ("Location Requirement", "required", "unspecified"),
        ("About Open Intelligence", "required", "unspecified"),
        ("What You'll Be Doing:", "preferred", "unspecified"),
        ("What We'll Give You:", "required", "unspecified"),
    ],
)
def test_public_job_posting_headings_classify_or_reset_sections(
    heading, current_section, expected_section
):
    assert _line_section(heading, current_section) == (expected_section, True)


def test_about_experience_prose_is_not_mistaken_for_a_heading():
    assert _line_section("About ten years of experience", "required") == (
        "required",
        False,
    )


def test_public_posting_heading_sequence_drives_profile_match_sections(
    authenticated_client,
):
    client = authenticated_client
    skills = {
        name: _add_private_skill(client, name, category)
        for name, category in (
            ("Python", "language"),
            ("SQL", "language"),
            ("Apache Spark", "tool"),
            ("Docker", "tool"),
        )
    }
    spark_alias = client.post(
        f"/skills/{skills['Apache Spark']['id']}/aliases",
        json={"alias": "spark"},
    )
    assert spark_alias.status_code == 201

    added = client.post(
        "/users/me/skills",
        json={"skill_id": skills["Python"]["id"]},
    )
    assert added.status_code == 201

    response = client.post(
        "/job-analysis",
        json={
            "text": (
                "What You'll Be Doing:\nPython\n"
                "Who We Are Looking For\nDocker\n"
                "What You Will Need\nSQL\n"
                "Nice to Have\nLanguages: Python, Spark\n"
                "Who You Are:\nDocker"
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    extracted = {skill["name"]: skill for skill in body["skills"]}
    assert extracted["Python"]["occurrences"][0]["section"] == "unspecified"
    assert extracted["SQL"]["occurrences"][0]["section"] == "required"
    assert extracted["Apache Spark"]["occurrences"][0]["section"] == "preferred"
    assert [
        occurrence["section"]
        for occurrence in extracted["Docker"]["occurrences"]
    ] == ["required", "unspecified"]
    assert body["profile_match"]["required"]["missing_skills"] == [
        "Docker",
        "SQL",
    ]
    assert body["profile_match"]["preferred"]["missing_skills"] == ["Apache Spark"]
    assert body["profile_match"]["unspecified"]["match_percentage"] == 50.0


def test_public_posting_excited_headings_drive_skill_sections(authenticated_client):
    client = authenticated_client
    skills = {
        name: _add_private_skill(client, name, category)
        for name, category in (
            ("Python", "language"),
            ("Docker", "tool"),
            ("SQL", "language"),
        )
    }

    response = client.post(
        "/job-analysis",
        json={
            "text": (
                "Minimum Qualifications\n"
                "Python\n"
                "You’re excited about this opportunity because you will…\n"
                "Docker\n"
                "We’re excited about you because you have…\n"
                "SQL"
            )
        },
    )

    assert response.status_code == 200
    extracted = {skill["name"]: skill for skill in response.json()["skills"]}
    assert extracted["Python"]["occurrences"][0]["section"] == "required"
    assert extracted["Docker"]["occurrences"][0]["section"] == "unspecified"
    assert extracted["SQL"]["occurrences"][0]["section"] == "required"


def test_compensation_heading_resets_requirement_section(authenticated_client):
    client = authenticated_client
    _add_private_skill(client, "Python", "language")
    _add_private_skill(client, "Docker", "tool")

    response = client.post(
        "/job-analysis",
        json={"text": "Minimum Qualifications\nPython\nCompensation\nDocker"},
    )

    assert response.status_code == 200
    extracted = {skill["name"]: skill for skill in response.json()["skills"]}
    assert extracted["Python"]["occurrences"][0]["section"] == "required"
    assert extracted["Docker"]["occurrences"][0]["section"] == "unspecified"


def test_official_genai_posting_technical_skills_heading_preserves_requirement_context(
    authenticated_client,
):
    client = authenticated_client
    _add_private_skill(client, "Python", "language")
    _add_private_skill(client, "PyTorch", "framework")
    _add_private_skill(client, "Azure", "cloud")

    response = client.post(
        "/job-analysis",
        json={
            "text": (
                "Qualifications:\n"
                "Technical Skills:\n"
                "Python, PyTorch\n"
                "Preferred:\n"
                "Azure"
            )
        },
    )

    assert response.status_code == 200
    extracted = {skill["name"]: skill for skill in response.json()["skills"]}
    assert extracted["Python"]["occurrences"][0]["section"] == "required"
    assert extracted["PyTorch"]["occurrences"][0]["section"] == "required"
    assert extracted["Azure"]["occurrences"][0]["section"] == "preferred"


def test_official_infrastructure_posting_bring_and_look_for_headings_are_required(
    authenticated_client,
):
    client = authenticated_client
    _add_private_skill(client, "Docker", "tool")
    _add_private_skill(client, "Kubernetes", "tool")
    _add_private_skill(client, "Python", "language")

    response = client.post(
        "/job-analysis",
        json={
            "text": (
                "What you will do\n"
                "Docker\n"
                "What you will bring with you\n"
                "Kubernetes\n"
                "What we look for\n"
                "Python"
            )
        },
    )

    assert response.status_code == 200
    extracted = {skill["name"]: skill for skill in response.json()["skills"]}
    assert extracted["Docker"]["occurrences"][0]["section"] == "unspecified"
    assert extracted["Kubernetes"]["occurrences"][0]["section"] == "required"
    assert extracted["Python"]["occurrences"][0]["section"] == "required"


def test_official_rocket_lab_qualification_headings_separate_required_and_nice_to_have(
    authenticated_client,
):
    client = authenticated_client
    _add_private_skill(client, "C++", "language")
    _add_private_skill(client, "Python", "language")

    response = client.post(
        "/job-analysis",
        json={
            "text": (
                "YOU'LL BRING THESE QUALIFICATIONS:\n"
                "C++ development\n"
                "THESE QUALIFICATIONS WOULD BE NICE TO HAVE:\n"
                "Python development"
            )
        },
    )

    assert response.status_code == 200
    extracted = {skill["name"]: skill for skill in response.json()["skills"]}
    assert extracted["C++"]["occurrences"][0]["section"] == "required"
    assert extracted["Python"]["occurrences"][0]["section"] == "preferred"


def test_fit_if_heading_is_required_and_helpful_not_required_is_preferred(
    authenticated_client,
):
    client = authenticated_client
    _add_private_skill(client, "AWS", "cloud")
    _add_private_skill(client, "Rust", "language")

    response = client.post(
        "/job-analysis",
        json={
            "text": (
                "YOU MIGHT BE A FIT IF YOU HAVE:\n"
                "AWS infrastructure experience\n"
                "Helpful (not required)\n"
                "Rust experience"
            )
        },
    )

    assert response.status_code == 200
    extracted = {skill["name"]: skill for skill in response.json()["skills"]}
    assert extracted["AWS"]["occurrences"][0]["section"] == "required"
    assert extracted["Rust"]["occurrences"][0]["section"] == "preferred"

def test_need_to_know_and_must_have_headings_keep_skill_sections_distinct(
    authenticated_client,
):
    client = authenticated_client
    _add_private_skill(client, "Docker", "tool")
    _add_private_skill(client, "Python", "language")
    _add_private_skill(client, "React", "framework")
    _add_private_skill(client, "AWS", "cloud")
    _add_private_skill(client, "Kubernetes", "tool")

    response = client.post(
        "/job-analysis",
        json={
            "text": (
                "What you'll do:\n"
                "Docker duties\n"
                "What we need from you:\n"
                "Python experience\n"
                "What we expect you to know:\n"
                "React experience\n"
                "Must-haves:\n"
                "AWS experience\n"
                "Nice-to-haves:\n"
                "Kubernetes experience"
            )
        },
    )

    assert response.status_code == 200
    extracted = {skill["name"]: skill for skill in response.json()["skills"]}
    assert extracted["Docker"]["occurrences"][0]["section"] == "unspecified"
    assert extracted["Python"]["occurrences"][0]["section"] == "required"
    assert extracted["React"]["occurrences"][0]["section"] == "required"
    assert extracted["AWS"]["occurrences"][0]["section"] == "required"
    assert extracted["Kubernetes"]["occurrences"][0]["section"] == "preferred"


def test_live_posting_skill_headings_classify_required_and_preferred_sections(
    authenticated_client,
):
    client = authenticated_client
    _add_private_skill(client, "Java", "language")
    _add_private_skill(client, "Python", "language")
    _add_private_skill(client, "AWS", "cloud")
    _add_private_skill(client, "React", "framework")
    _add_private_skill(client, "Docker", "tool")
    _add_private_skill(client, "Kubernetes", "tool")

    response = client.post(
        "/job-analysis",
        json={
            "text": (
                "What you'll do:\nDocker tasks\n"
                "Required skills and experience:\nJava\n"
                "Skills & Experience:\nPython\n"
                "Technical Skills & Experience:\nAWS\n"
                "Who you are:\nReact\n"
                "You might be a great fit if you:\nKubernetes\n"
                "Nice-to-have:\nDocker"
            )
        },
    )

    assert response.status_code == 200
    extracted = {skill["name"]: skill for skill in response.json()["skills"]}
    assert extracted["Docker"]["occurrences"][0]["section"] == "unspecified"
    assert extracted["Java"]["occurrences"][0]["section"] == "required"
    assert extracted["Python"]["occurrences"][0]["section"] == "required"
    assert extracted["AWS"]["occurrences"][0]["section"] == "required"
    assert extracted["React"]["occurrences"][0]["section"] == "unspecified"
    assert extracted["Kubernetes"]["occurrences"][0]["section"] == "required"
    assert extracted["Docker"]["occurrences"][1]["section"] == "preferred"


def test_required_qualification_heading_variants_keep_preferred_sections_distinct(
    authenticated_client,
):
    client = authenticated_client
    _add_private_skill(client, "Java", "language")
    _add_private_skill(client, "Python", "language")
    _add_private_skill(client, "AWS", "cloud")
    _add_private_skill(client, "React", "framework")
    _add_private_skill(client, "Rust", "language")

    response = client.post(
        "/job-analysis",
        json={
            "text": (
                "What We're Looking For (Required):\nJava\n"
                "Skills and Qualifications:\nPython\n"
                "Essential:\nAWS\n"
                "Required Skills & Qualifications:\nReact\n"
                "Nice to have:\nRust"
            )
        },
    )

    assert response.status_code == 200
    extracted = {skill["name"]: skill for skill in response.json()["skills"]}
    for name in ("Java", "Python", "AWS", "React"):
        assert extracted[name]["occurrences"][0]["section"] == "required"
    assert extracted["Rust"]["occurrences"][0]["section"] == "preferred"



def test_bring_to_role_and_experience_headings_classify_requirements(authenticated_client):
    client = authenticated_client
    for name, category in (
        ("Python", "language"),
        ("AWS", "cloud"),
        ("Docker", "tool"),
        ("Kubernetes", "tool"),
        ("React", "framework"),
        ("Rust", "language"),
    ):
        _add_private_skill(client, name, category)

    response = client.post(
        "/job-analysis",
        json={
            "text": (
                "What You Bring to the Role:\nPython\n"
                "What You Bring to the Table:\nAWS\n"
                "What You Bring With You:\nDocker\n"
                "Your Skills and Experience:\nKubernetes\n"
                "Your Qualifications:\nReact\n"
                "Your Impact:\nRust"
            )
        },
    )

    assert response.status_code == 200
    extracted = {skill["name"]: skill for skill in response.json()["skills"]}
    actual_sections = {
        name: extracted[name]["occurrences"][0]["section"]
        for name in ("Python", "AWS", "Docker", "Kubernetes", "React", "Rust")
    }
    assert actual_sections == {
        "Python": "required",
        "AWS": "required",
        "Docker": "required",
        "Kubernetes": "required",
        "React": "required",
        "Rust": "unspecified",
    }


def test_what_it_takes_and_what_you_have_headings_classify_requirements(
    authenticated_client,
):
    client = authenticated_client
    _add_private_skill(client, "Python", "language")
    _add_private_skill(client, "FastAPI", "framework")
    _add_private_skill(client, "AWS", "cloud")
    _add_private_skill(client, "Docker", "tool")
    _add_private_skill(client, "Kubernetes", "tool")
    _add_private_skill(client, "TypeScript", "language")
    _add_private_skill(client, "React", "framework")

    response = client.post(
        "/job-analysis",
        json={
            "text": (
                "What You Have:\nPython\n"
                "What It Takes:\nFastAPI\n"
                "Have You Got What It Takes?\nAWS\n"
                "What We Require:\nDocker\n"
                "Qualifications You Will Bring:\nKubernetes\n"
                "What It Takes to Be Successful:\nTypeScript\n"
                "Bonus Points:\nReact"
            )
        },
    )

    assert response.status_code == 200
    extracted = {skill["name"]: skill for skill in response.json()["skills"]}
    for name in ("Python", "FastAPI", "AWS", "Docker", "Kubernetes", "TypeScript"):
        assert extracted[name]["occurrences"][0]["section"] == "required"
    assert extracted["React"]["occurrences"][0]["section"] == "preferred"

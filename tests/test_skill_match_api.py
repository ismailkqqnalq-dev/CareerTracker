def _create_skill(client, name):
    response = client.post(
        "/skills",
        json={"name": name, "category": "technology"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_opportunity(client, headers=None):
    response = client.post(
        "/opportunities",
        headers=headers,
        json={
            "company": "Test Company",
            "position": "Data Analyst",
            "type": "full-time",
            "application_date": "2026-10-01",
            "job_link": "https://example.com/job",
            "salary": 50000,
            "location": "Remote",
            "status": "Applied",
            "notes": "",
            "next_action": "",
            "last_contact_date": "2026-10-01",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_skill_match_returns_matched_and_missing_skills(
    authenticated_client,
):
    client = authenticated_client
    python_skill = _create_skill(client, "Python")
    sql_skill = _create_skill(client, "SQL")
    excel_skill = _create_skill(client, "Excel")
    opportunity_id = _create_opportunity(client)

    for skill_name in ("Python", "SQL", "Excel"):
        attached = client.post(
            f"/opportunities/{opportunity_id}/skills",
            json={"skill": skill_name},
        )
        assert attached.status_code == 201, attached.text

    profile_skill = client.post(
        "/users/me/skills",
        json={
            "skill_id": python_skill["id"],
            "proficiency_level": "intermediate",
            "years_experience": 2,
        },
    )
    assert profile_skill.status_code == 201, profile_skill.text

    response = client.get(
        f"/opportunities/{opportunity_id}/skill-match"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["opportunity_id"] == opportunity_id
    assert body["required_skill_count"] == 3
    assert body["matched_skill_count"] == 1
    assert body["match_percentage"] == 33.33
    assert [skill["name"] for skill in body["matched_skills"]] == ["Python"]
    assert [skill["name"] for skill in body["missing_skills"]] == [
        "Excel",
        "SQL",
    ]


def test_skill_match_with_no_requirements_returns_zero_percent(
    authenticated_client,
):
    opportunity_id = _create_opportunity(authenticated_client)

    response = authenticated_client.get(
        f"/opportunities/{opportunity_id}/skill-match"
    )

    assert response.status_code == 200
    assert response.json()["required_skill_count"] == 0
    assert response.json()["matched_skill_count"] == 0
    assert response.json()["match_percentage"] == 0
    assert response.json()["matched_skills"] == []
    assert response.json()["missing_skills"] == []


def test_skill_match_for_unknown_opportunity_returns_404(
    authenticated_client,
):
    response = authenticated_client.get(
        "/opportunities/999999/skill-match"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Opportunity not found: 999999",
        "error_code": "opportunity_not_found",
    }


def test_skill_match_requires_login(client):
    response = client.get("/opportunities/1/skill-match")

    assert response.status_code == 401

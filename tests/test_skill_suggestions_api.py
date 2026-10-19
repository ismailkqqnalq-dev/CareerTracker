def _create_opportunity(client):
    response = client.post(
        "/opportunities",
        json={
            "company": "Suggestion Test Co",
            "position": "Engineer",
            "type": "full-time",
            "application_date": "2026-10-19",
            "job_link": "https://example.com/job",
            "salary": 1000,
            "location": "Istanbul",
            "status": "Applied",
            "notes": "Test opportunity",
            "next_action": "Follow up",
            "last_contact_date": "2026-10-19",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_unknown_opportunity_skill_is_saved_for_review(authenticated_client):
    client = authenticated_client
    opportunity_id = _create_opportunity(client)

    response = client.post(
        f"/opportunities/{opportunity_id}/skills",
        json={"skill": "  New   Data Tool  "},
    )

    assert response.status_code == 404
    assert "saved for review" in response.json()["detail"]

    suggestions = client.get("/skills/suggestions")
    assert suggestions.status_code == 200
    assert suggestions.json()[0]["raw_name"] == "New   Data Tool"
    assert suggestions.json()[0]["normalized_name"] == "new data tool"
    assert suggestions.json()[0]["status"] == "pending"


def test_skill_suggestion_submissions_are_normalized_and_idempotent(
    authenticated_client,
):
    client = authenticated_client

    first = client.post("/skills/suggestions", json={"skill": "  PyTorch  "})
    duplicate = client.post("/skills/suggestions", json={"skill": "PYTORCH"})

    assert first.status_code == 201
    assert duplicate.status_code == 200
    assert first.json()["id"] == duplicate.json()["id"]
    assert duplicate.json()["normalized_name"] == "pytorch"
    assert len(client.get("/skills/suggestions").json()) == 1


def test_user_can_map_suggestion_and_reuse_it_for_opportunity_skill(
    authenticated_client,
):
    client = authenticated_client
    created_skill = client.post(
        "/skills",
        json={"name": "React", "category": "framework"},
    )
    assert created_skill.status_code == 201
    skill_id = created_skill.json()["id"]
    opportunity_id = _create_opportunity(client)
    unknown_name = "React-Express-Integration"

    unknown_response = client.post(
        f"/opportunities/{opportunity_id}/skills",
        json={"skill": unknown_name},
    )
    assert unknown_response.status_code == 404

    suggestion = client.get("/skills/suggestions").json()[0]
    mapped = client.patch(
        f"/skills/suggestions/{suggestion['id']}",
        json={"skill_id": skill_id},
    )

    assert mapped.status_code == 200
    assert mapped.json()["status"] == "accepted"
    assert mapped.json()["resolved_skill_id"] == skill_id

    attached = client.post(
        f"/opportunities/{opportunity_id}/skills",
        json={"skill": unknown_name},
    )
    assert attached.status_code == 201
    assert attached.json()["name"] == "React"

    resolved = client.get(
        "/skills/resolve",
        params={"name": unknown_name},
    )
    assert resolved.status_code == 200
    assert resolved.json()["id"] == skill_id


def test_suggestion_mapping_is_private_to_its_owner(client):
    client.post(
        "/auth/register",
        json={"email": "first@example.com", "password": "StrongPass123"},
    )
    first_token = client.post(
        "/auth/token",
        data={"username": "first@example.com", "password": "StrongPass123"},
    ).json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {first_token}"})

    created_skill = client.post("/skills", json={"name": "Python"})
    skill_id = created_skill.json()["id"]
    submitted = client.post(
        "/skills/suggestions",
        json={"skill": "My Private Python Variant"},
    )
    suggestion_id = submitted.json()["id"]
    assert client.patch(
        f"/skills/suggestions/{suggestion_id}",
        json={"skill_id": skill_id},
    ).status_code == 200

    client.post(
        "/auth/register",
        json={"email": "second@example.com", "password": "StrongPass123"},
    )
    second_token = client.post(
        "/auth/token",
        data={"username": "second@example.com", "password": "StrongPass123"},
    ).json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {second_token}"})

    assert client.get(
        "/skills/resolve",
        params={"name": "My Private Python Variant"},
    ).status_code == 404
    assert client.get("/skills/suggestions").json() == []


def test_cannot_map_suggestion_to_unknown_skill(authenticated_client):
    client = authenticated_client
    submitted = client.post(
        "/skills/suggestions",
        json={"skill": "Unknown Alias"},
    )

    response = client.patch(
        f"/skills/suggestions/{submitted.json()['id']}",
        json={"skill_id": 9999},
    )

    assert response.status_code == 404


def test_known_skill_cannot_be_submitted_as_unknown_suggestion(
    authenticated_client,
):
    client = authenticated_client
    assert client.post("/skills", json={"name": "React"}).status_code == 201

    response = client.post(
        "/skills/suggestions",
        json={"skill": "  REACT  "},
    )

    assert response.status_code == 409


def test_skill_catalog_can_be_listed_for_mapping_picker(authenticated_client):
    client = authenticated_client
    client.post("/skills", json={"name": "Python"})
    client.post("/skills", json={"name": "React"})

    response = client.get("/skills")

    assert response.status_code == 200
    assert [skill["name"] for skill in response.json()] == ["Python", "React"]


def test_candidates_rank_similar_catalog_skill_first(authenticated_client):
    client = authenticated_client
    python = client.post("/skills", json={"name": "Python"}).json()
    client.post("/skills", json={"name": "JavaScript"})
    suggestion = client.post(
        "/skills/suggestions",
        json={"skill": "Pythno"},
    ).json()

    response = client.get(
        f"/skills/suggestions/{suggestion['id']}/candidates"
    )

    assert response.status_code == 200
    assert response.json()[0]["id"] == python["id"]
    assert response.json()[0]["name"] == "Python"
    assert 0.25 <= response.json()[0]["score"] <= 1


def test_candidate_search_does_not_show_irrelevant_skills(authenticated_client):
    client = authenticated_client
    client.post("/skills", json={"name": "Python"})
    suggestion = client.post(
        "/skills/suggestions",
        json={"skill": "zzqqvv-unrelated"},
    ).json()

    response = client.get(
        f"/skills/suggestions/{suggestion['id']}/candidates"
    )

    assert response.status_code == 200
    assert response.json() == []


def test_candidate_search_is_private_and_requires_pending_suggestion(
    authenticated_client,
):
    client = authenticated_client
    skill = client.post("/skills", json={"name": "Python"}).json()
    suggestion = client.post(
        "/skills/suggestions",
        json={"skill": "Pythno"},
    ).json()
    assert client.patch(
        f"/skills/suggestions/{suggestion['id']}",
        json={"skill_id": skill["id"]},
    ).status_code == 200

    response = client.get(
        f"/skills/suggestions/{suggestion['id']}/candidates"
    )

    assert response.status_code == 409


def test_candidate_limit_must_be_between_one_and_ten(authenticated_client):
    client = authenticated_client
    suggestion = client.post(
        "/skills/suggestions",
        json={"skill": "SomeUnknownSkill"},
    ).json()

    response = client.get(
        f"/skills/suggestions/{suggestion['id']}/candidates",
        params={"limit": 11},
    )

    assert response.status_code == 422


def test_skill_suggestions_require_authentication(client):
    response = client.get("/skills/suggestions")

    assert response.status_code == 401

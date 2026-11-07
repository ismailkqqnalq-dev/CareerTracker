from app.database.session import get_db
from app.main import app
from app.models.skills import PersonalSkillAlias, Skill, SkillAliases, SkillSuggestion
from app.models.users import User
from app.services.semantic_skill_candidate_service import (
    SemanticModelUnavailable,
    get_semantic_embedder,
)
from app.services.skill_normalizer import normalize_text


class FakeSemanticEmbedder:
    def embed_texts(self, texts):
        vectors = []
        for text in texts:
            folded = text.casefold()
            if "web api" in folded or "fastapi" in folded or "fast api" in folded:
                vectors.append((1.0, 0.0))
            elif "react" in folded:
                vectors.append((0.0, 1.0))
            else:
                vectors.append((0.0, 0.0))
        return vectors


class UnavailableSemanticEmbedder:
    def embed_texts(self, _texts):
        raise SemanticModelUnavailable


class FailingSemanticEmbedder:
    def embed_texts(self, _texts):
        from app.services.semantic_skill_candidate_service import SemanticEngineFailed

        raise SemanticEngineFailed


class TrackingSemanticEmbedder(FakeSemanticEmbedder):
    def __init__(self):
        self.texts = []

    def embed_texts(self, texts):
        self.texts.extend(texts)
        return super().embed_texts(texts)


def _create_skill(client, name):
    response = client.post("/skills", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def _pending_suggestion(client, raw_name, email="owner@example.com"):
    generator = app.dependency_overrides[get_db]()
    db = next(generator)
    try:
        user = db.query(User).filter(User.email == email).one()
        suggestion = SkillSuggestion(
            user_id=user.id,
            raw_name=raw_name,
            normalized_name=normalize_text(raw_name),
            status="pending",
        )
        db.add(suggestion)
        db.commit()
        return suggestion.id
    finally:
        generator.close()


def _use_embedder(embedder):
    app.dependency_overrides[get_semantic_embedder] = lambda: embedder


def test_semantic_candidate_strategy_uses_local_encoder_and_keeps_response_shape(
    authenticated_client,
):
    client = authenticated_client
    fastapi = _create_skill(client, "FastAPI")
    _create_skill(client, "React")
    suggestion_id = _pending_suggestion(client, "web api services")
    _use_embedder(FakeSemanticEmbedder())

    try:
        response = client.get(
            f"/skills/suggestions/{suggestion_id}/candidates?strategy=semantic"
        )
    finally:
        app.dependency_overrides.pop(get_semantic_embedder, None)

    assert response.status_code == 200, response.text
    assert response.json()[0]["id"] == fastapi["id"]
    assert set(response.json()[0]) == {"id", "name", "category", "score"}
    assert 0.0 <= response.json()[0]["score"] <= 1.0


def test_semantic_candidates_are_unavailable_without_a_local_model(
    authenticated_client,
):
    client = authenticated_client
    _create_skill(client, "FastAPI")
    suggestion_id = _pending_suggestion(client, "web api services")
    _use_embedder(UnavailableSemanticEmbedder())

    try:
        response = client.get(
            f"/skills/suggestions/{suggestion_id}/candidates?strategy=semantic"
        )
    finally:
        app.dependency_overrides.pop(get_semantic_embedder, None)

    assert response.status_code == 503
    assert response.json()["error_code"] == "semantic_engine_unavailable"


def test_semantic_candidates_still_require_authentication(client):
    response = client.get(
        "/skills/suggestions/1/candidates?strategy=semantic"
    )

    assert response.status_code == 401


def test_semantic_candidate_requests_are_rate_limited_per_user(
    authenticated_client, monkeypatch
):
    from app.rate_limits import get_rate_limit_settings

    monkeypatch.setenv("RATE_LIMIT_SEMANTIC_CANDIDATES_PER_USER_PER_MINUTE", "1")
    get_rate_limit_settings.cache_clear()
    client = authenticated_client
    _create_skill(client, "FastAPI")
    suggestion_id = _pending_suggestion(client, "web api services")
    _use_embedder(FakeSemanticEmbedder())

    try:
        first = client.get(
            f"/skills/suggestions/{suggestion_id}/candidates?strategy=semantic"
        )
        second = client.get(
            f"/skills/suggestions/{suggestion_id}/candidates?strategy=semantic"
        )
        lexical = client.get(
            f"/skills/suggestions/{suggestion_id}/candidates?strategy=lexical"
        )

        assert client.post(
            "/auth/register",
            json={"email": "second@example.com", "password": "StrongPass123"},
        ).status_code == 201
        second_token = client.post(
            "/auth/token",
            data={"username": "second@example.com", "password": "StrongPass123"},
        ).json()["access_token"]
        client.headers["Authorization"] = f"Bearer {second_token}"
        _create_skill(client, "React")
        second_suggestion_id = _pending_suggestion(
            client, "web api services", "second@example.com"
        )
        other_user = client.get(
            f"/skills/suggestions/{second_suggestion_id}/candidates?strategy=semantic"
        )
    finally:
        app.dependency_overrides.pop(get_semantic_embedder, None)
        get_rate_limit_settings.cache_clear()

    assert first.status_code == 200, first.text
    assert second.status_code == 429
    assert second.json()["error_code"] == "rate_limited"
    assert int(second.headers["Retry-After"]) >= 1
    assert lexical.status_code == 200, lexical.text
    assert other_user.status_code == 200, other_user.text


def test_default_candidate_strategy_remains_lexical_without_semantic_model(
    authenticated_client,
):
    client = authenticated_client
    fastapi = _create_skill(client, "FastAPI")
    _create_skill(client, "React")
    suggestion_id = _pending_suggestion(client, "FastAP1")

    response = client.get(f"/skills/suggestions/{suggestion_id}/candidates")

    assert response.status_code == 200, response.text
    assert response.json()[0]["id"] == fastapi["id"]


def test_semantic_strategy_reports_engine_failure_with_error_code(
    authenticated_client,
):
    client = authenticated_client
    _create_skill(client, "FastAPI")
    suggestion_id = _pending_suggestion(client, "web api services")
    _use_embedder(FailingSemanticEmbedder())

    try:
        response = client.get(
            f"/skills/suggestions/{suggestion_id}/candidates?strategy=semantic"
        )
    finally:
        app.dependency_overrides.pop(get_semantic_embedder, None)

    assert response.status_code == 502
    assert response.json()["error_code"] == "semantic_engine_failed"


def test_personal_aliases_are_not_used_for_other_users_semantic_candidates(
    authenticated_client,
):
    client = authenticated_client
    generator = app.dependency_overrides[get_db]()
    db = next(generator)
    try:
        owner = db.query(User).filter(User.email == "owner@example.com").one()
        shared_skill = Skill(name="SharedAnalyticsTool", category="tool")
        db.add(shared_skill)
        db.flush()
        db.add(SkillAliases(alias="sharedanalyticstool", skill_id=shared_skill.id))
        db.add(
            PersonalSkillAlias(
                user_id=owner.id,
                alias="owner only semantic phrase",
                skill_id=shared_skill.id,
            )
        )
        db.commit()
    finally:
        generator.close()

    client.post(
        "/auth/register",
        json={"email": "other@example.com", "password": "StrongPass123"},
    )
    token = client.post(
        "/auth/token",
        data={"username": "other@example.com", "password": "StrongPass123"},
    ).json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    suggestion_id = _pending_suggestion(client, "shared analytics", "other@example.com")
    embedder = TrackingSemanticEmbedder()
    _use_embedder(embedder)

    try:
        response = client.get(
            f"/skills/suggestions/{suggestion_id}/candidates?strategy=semantic"
        )
    finally:
        app.dependency_overrides.pop(get_semantic_embedder, None)

    assert response.status_code == 200, response.text
    assert "owner only semantic phrase" not in embedder.texts


def test_semantic_candidates_do_not_expose_another_users_private_skills(
    authenticated_client,
):
    client = authenticated_client
    private_skill = _create_skill(client, "PrivateVectorDB")
    client.post(
        "/auth/register",
        json={"email": "other@example.com", "password": "StrongPass123"},
    )
    token = client.post(
        "/auth/token",
        data={"username": "other@example.com", "password": "StrongPass123"},
    ).json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    own_skill = _create_skill(client, "React")
    suggestion_id = _pending_suggestion(client, "web api services", "other@example.com")
    _use_embedder(FakeSemanticEmbedder())

    try:
        response = client.get(
            f"/skills/suggestions/{suggestion_id}/candidates?strategy=semantic"
        )
    finally:
        app.dependency_overrides.pop(get_semantic_embedder, None)

    assert response.status_code == 200, response.text
    ids = {candidate["id"] for candidate in response.json()}
    assert private_skill["id"] not in ids
    assert own_skill["id"] in ids

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import auth_service
from app.security import registration_is_enabled
from app.models.activities import Activity
from app.models.contacts import Contact
from app.models.opportunity import Opportunity
from app.models.opportunity_skills import OpportunitySkill
from app.models.skills import (
    PersonalSkillAlias,
    Skill,
    SkillAliases,
    SkillSuggestion,
    UserSkill,
)
from app.models.tasks import Task
from app.models.users import User


def register(client, email="test@example.com", password="StrongPass123"):
    return client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )


def test_register_user_returns_public_data_only(client):
    response = register(client)

    assert response.status_code == 201
    assert response.json()["email"] == "test@example.com"
    assert "hashed_password" not in response.json()


def test_register_duplicate_email_returns_409(client):
    assert register(client).status_code == 201

    response = register(client, email="TEST@example.com")

    assert response.status_code == 409


def test_login_and_get_current_user(client):
    register(client)

    login_response = client.post(
        "/auth/token",
        data={
            "username": "test@example.com",
            "password": "StrongPass123",
        },
    )

    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert me_response.status_code == 200
    assert me_response.json()["email"] == "test@example.com"


def test_login_with_wrong_password_returns_401(client):
    register(client)

    response = client.post(
        "/auth/token",
        data={
            "username": "test@example.com",
            "password": "WrongPassword123",
        },
    )

    assert response.status_code == 401


def test_me_without_token_returns_401(client):
    response = client.get("/auth/me")

    assert response.status_code == 401


def _seed_account_deletion_records(db_session, owner_email="owner@example.com"):
    owner = db_session.query(User).filter_by(email=owner_email).one()
    other = User(
        email="other-account@example.com",
        hashed_password="not-used-in-this-test",
        is_active=True,
    )
    db_session.add(other)
    db_session.flush()

    shared_skill = Skill(name="SharedAccountDeletionTest", category="tool")
    owner_skill = Skill(
        name="OwnerAccountDeletionTest", category="tool", owner_user_id=owner.id
    )
    other_skill = Skill(
        name="OtherAccountDeletionTest", category="tool", owner_user_id=other.id
    )
    db_session.add_all([shared_skill, owner_skill, other_skill])
    db_session.flush()

    db_session.add_all(
        [
            SkillAliases(alias="sharedaccountdeletiontest", skill_id=shared_skill.id),
            PersonalSkillAlias(
                user_id=owner.id,
                alias="owneraccountdeletionalias",
                skill_id=owner_skill.id,
            ),
            PersonalSkillAlias(
                user_id=other.id,
                alias="otheraccountdeletionalias",
                skill_id=other_skill.id,
            ),
            UserSkill(user_id=owner.id, skill_id=owner_skill.id),
            SkillSuggestion(
                user_id=owner.id,
                raw_name="Owner Suggested Deletion Skill",
                normalized_name="ownersuggesteddeletionskill",
                resolved_skill_id=shared_skill.id,
                status="accepted",
            ),
            SkillSuggestion(
                user_id=other.id,
                raw_name="Other Suggested Deletion Skill",
                normalized_name="othersuggesteddeletionskill",
                status="pending",
            ),
        ]
    )

    owner_opportunity = Opportunity(user_id=owner.id, company="Owner company")
    other_opportunity = Opportunity(user_id=other.id, company="Other company")
    db_session.add_all([owner_opportunity, other_opportunity])
    db_session.flush()

    owner_contact = Contact(user_id=owner.id, name="Owner contact", opportunity_id=owner_opportunity.id)
    other_contact = Contact(user_id=other.id, name="Other contact", opportunity_id=other_opportunity.id)
    db_session.add_all([owner_contact, other_contact])
    db_session.flush()
    db_session.add_all(
        [
            Task(user_id=owner.id, opportunity_id=owner_opportunity.id, description="Owner task"),
            Task(user_id=other.id, opportunity_id=other_opportunity.id, description="Other task"),
            Activity(
                user_id=owner.id,
                opportunity_id=owner_opportunity.id,
                contact_id=owner_contact.id,
                activity_type="call",
            ),
            Activity(
                user_id=other.id,
                opportunity_id=other_opportunity.id,
                contact_id=other_contact.id,
                activity_type="call",
            ),
            OpportunitySkill(opportunity_id=owner_opportunity.id, skill_id=shared_skill.id),
            OpportunitySkill(opportunity_id=owner_opportunity.id, skill_id=owner_skill.id),
            OpportunitySkill(opportunity_id=other_opportunity.id, skill_id=other_skill.id),
        ]
    )
    db_session.commit()
    return owner.id, other.id


def test_delete_account_requires_the_current_password_and_keeps_data_on_failure(
    authenticated_client, db_session
):
    client = authenticated_client
    owner_id, _other_id = _seed_account_deletion_records(db_session)

    response = client.request("DELETE", "/auth/me", json={"password": "WrongPass123"})

    assert response.status_code == 403
    assert response.json()["error_code"] == "password_confirmation_failed"
    assert client.get("/auth/me").status_code == 200
    assert db_session.get(User, owner_id) is not None
    assert db_session.query(Opportunity).filter_by(user_id=owner_id).count() == 1


def test_delete_account_cascades_only_the_current_users_data(
    authenticated_client, db_session
):
    client = authenticated_client
    owner_id, other_id = _seed_account_deletion_records(db_session)
    shared_skill_id = (
        db_session.query(Skill)
        .filter_by(name="SharedAccountDeletionTest")
        .one()
        .id
    )

    response = client.request(
        "DELETE", "/auth/me", json={"password": "StrongPass123"}
    )

    assert response.status_code == 204
    assert client.get("/auth/me").status_code == 401
    assert db_session.get(User, owner_id) is None
    assert db_session.query(Opportunity).filter_by(user_id=owner_id).count() == 0
    assert db_session.query(Contact).filter_by(user_id=owner_id).count() == 0
    assert db_session.query(Task).filter_by(user_id=owner_id).count() == 0
    assert db_session.query(Activity).filter_by(user_id=owner_id).count() == 0
    assert db_session.query(UserSkill).filter_by(user_id=owner_id).count() == 0
    assert db_session.query(PersonalSkillAlias).filter_by(user_id=owner_id).count() == 0
    assert db_session.query(SkillSuggestion).filter_by(user_id=owner_id).count() == 0
    assert db_session.query(Skill).filter_by(name="OwnerAccountDeletionTest").count() == 0
    assert db_session.get(Skill, shared_skill_id) is not None
    assert (
        db_session.query(SkillAliases)
        .filter_by(alias="sharedaccountdeletiontest", skill_id=shared_skill_id)
        .count()
        == 1
    )

    assert db_session.get(User, other_id) is not None
    assert db_session.query(Opportunity).filter_by(user_id=other_id).count() == 1
    assert db_session.query(Contact).filter_by(user_id=other_id).count() == 1
    assert db_session.query(Task).filter_by(user_id=other_id).count() == 1
    assert db_session.query(Activity).filter_by(user_id=other_id).count() == 1
    assert db_session.query(Skill).filter_by(name="OtherAccountDeletionTest").count() == 1
    assert (
        db_session.query(PersonalSkillAlias)
        .filter_by(user_id=other_id, alias="otheraccountdeletionalias")
        .count()
        == 1
    )
    assert db_session.query(SkillSuggestion).filter_by(user_id=other_id).count() == 1
    assert (
        db_session.query(OpportunitySkill)
        .join(Opportunity, OpportunitySkill.opportunity_id == Opportunity.id)
        .filter(Opportunity.user_id == other_id)
        .count()
        == 1
    )


def test_delete_account_requires_authentication(client):
    response = client.request(
        "DELETE", "/auth/me", json={"password": "StrongPass123"}
    )

    assert response.status_code == 401

@pytest.mark.parametrize(
    "bad_secret",
    ["", "short", "x" * 31, "replace-with-a-random-secret"],
)
def test_app_rejects_invalid_jwt_secret_at_startup(monkeypatch, bad_secret):
    monkeypatch.setenv("JWT_SECRET_KEY", bad_secret)

    with pytest.raises(RuntimeError) as error:
        with TestClient(app):
            pass

    assert "JWT_SECRET_KEY" in str(error.value)
    if bad_secret:
        assert bad_secret not in str(error.value)


def test_app_accepts_a_32_byte_jwt_secret_at_startup(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 32)

    with TestClient(app) as test_client:
        assert test_client.get("/").status_code == 200


def test_registration_disabled_returns_structured_403(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("REGISTRATION_ENABLED", raising=False)

    response = register(client)

    assert response.status_code == 403
    assert response.json()["error_code"] == "registration_disabled"


def test_registration_can_be_explicitly_enabled_in_production(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("REGISTRATION_ENABLED", "true")

    assert register(client).status_code == 201


def test_login_verifies_a_dummy_hash_for_unknown_email(client, monkeypatch):
    calls = []

    def record_verification(password, encoded_hash):
        calls.append((password, encoded_hash))
        return False

    monkeypatch.setattr(auth_service, "verify_password", record_verification)
    response = client.post(
        "/auth/token",
        data={"username": "missing@example.com", "password": "WrongPass123"},
    )

    assert response.status_code == 401
    assert len(calls) == 1
    assert calls[0][0] == "WrongPass123"
    assert calls[0][1]


def test_login_verifies_stored_hash_for_existing_user(client, monkeypatch):
    assert register(client).status_code == 201
    calls = []

    def record_verification(password, encoded_hash):
        calls.append((password, encoded_hash))
        return True

    monkeypatch.setattr(auth_service, "verify_password", record_verification)
    response = client.post(
        "/auth/token",
        data={"username": "test@example.com", "password": "StrongPass123"},
    )

    assert response.status_code == 200
    assert len(calls) == 1
    assert calls[0][0] == "StrongPass123"
    assert calls[0][1]


@pytest.mark.parametrize("app_env", [None, "", "prod", "staging"])
def test_registration_defaults_closed_without_explicit_development(monkeypatch, app_env):
    monkeypatch.delenv("REGISTRATION_ENABLED", raising=False)
    if app_env is None:
        monkeypatch.delenv("APP_ENV", raising=False)
    else:
        monkeypatch.setenv("APP_ENV", app_env)

    assert registration_is_enabled() is False


@pytest.mark.parametrize("app_env", ["development", "DEVELOPMENT", " DeVeLoPmEnT "])
def test_registration_defaults_open_only_for_explicit_development(monkeypatch, app_env):
    monkeypatch.delenv("REGISTRATION_ENABLED", raising=False)
    monkeypatch.setenv("APP_ENV", app_env)

    assert registration_is_enabled() is True


@pytest.mark.parametrize("configured", ["sometimes", ""])
def test_registration_rejects_invalid_override(monkeypatch, configured):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("REGISTRATION_ENABLED", configured)

    with pytest.raises(RuntimeError, match="REGISTRATION_ENABLED"):
        registration_is_enabled()

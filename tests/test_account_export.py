from datetime import date, datetime

from app.database.session import Base
from app.models.activities import Activity
from app.models.contacts import Contact
from app.models.email_insights import EmailSuggestion, InboundAddress
from app.models.opportunity import Opportunity
from app.models.opportunity_skills import OpportunitySkill
from app.models.skills import PersonalSkillAlias, Skill, SkillSuggestion, UserSkill
from app.models.tasks import Task
from app.models.users import User
from app.services.account_export_service import EXPORTED_TABLES


def _seed(db, user, label, shared_skill):
    own_skill = Skill(name=f"{label} Skill", category="tool", owner_user_id=user.id)
    db.add(own_skill)
    db.flush()
    opportunity = Opportunity(
        user_id=user.id, company=f"{label} Company", position="Backend",
        application_date=datetime(2026, 11, 1, 9, 30), status="Applied",
    )
    db.add(opportunity)
    db.flush()
    contact = Contact(user_id=user.id, name=f"{label} Contact", opportunity_id=opportunity.id)
    db.add(contact)
    db.flush()
    db.add_all([
        OpportunitySkill(opportunity_id=opportunity.id, skill_id=shared_skill.id),
        OpportunitySkill(opportunity_id=opportunity.id, skill_id=own_skill.id),
        Activity(user_id=user.id, opportunity_id=opportunity.id, contact_id=contact.id,
                 activity_type="call", notes=f"{label} note"),
        Task(user_id=user.id, opportunity_id=opportunity.id, description=f"{label} task",
             due_date=datetime(2026, 11, 30)),
        UserSkill(user_id=user.id, skill_id=shared_skill.id, proficiency_level="advanced"),
        PersonalSkillAlias(user_id=user.id, alias=f"{label.lower()}-alias", skill_id=own_skill.id),
        SkillSuggestion(user_id=user.id, raw_name=f"{label} Raw", normalized_name=f"{label.lower()}raw"),
        InboundAddress(user_id=user.id, local_part=f"{label.lower()}-inbox"),
        EmailSuggestion(user_id=user.id, opportunity_id=opportunity.id, email_type="mulakat_daveti",
                        confidence=0.995, sender=f"hr@{label.lower()}.example", subject=f"{label} interview",
                        suggested_task_due_date=date(2026, 12, 2)),
    ])
    db.commit()


def _seed_two_accounts(db_session):
    owner = db_session.query(User).filter_by(email="owner@example.com").one()
    other = User(email="other@example.com", hashed_password="other-secret-hash", is_active=True)
    shared = Skill(name="Python", category="language")
    db_session.add_all([other, shared])
    db_session.flush()
    _seed(db_session, owner, "Owner", shared)
    _seed(db_session, other, "Other", shared)
    return owner


def test_export_contains_every_section_of_the_current_user_only(authenticated_client, db_session):
    owner = _seed_two_accounts(db_session)

    response = authenticated_client.get("/auth/me/export")

    assert response.status_code == 200
    document = response.json()
    assert document["format_version"] == 1
    assert document["account"]["email"] == "owner@example.com"
    assert document["opportunities"][0]["company"] == "Owner Company"
    assert document["opportunities"][0]["application_date"] == "2026-11-01T09:30:00"
    assert document["opportunities"][0]["skills"] == ["Owner Skill", "Python"]
    assert [row["notes"] for row in document["activities"]] == ["Owner note"]
    assert [row["name"] for row in document["contacts"]] == ["Owner Contact"]
    assert [row["description"] for row in document["tasks"]] == ["Owner task"]
    assert [row["name"] for row in document["custom_skills"]] == ["Owner Skill"]
    assert [(row["skill_name"], row["proficiency_level"]) for row in document["user_skills"]] == [("Python", "advanced")]
    assert [(row["alias"], row["skill_name"]) for row in document["personal_skill_aliases"]] == [("owner-alias", "Owner Skill")]
    assert [row["raw_name"] for row in document["skill_suggestions"]] == ["Owner Raw"]
    assert [row["local_part"] for row in document["email_forwarding_addresses"]] == ["owner-inbox"]
    suggestion = document["email_suggestions"][0]
    assert (suggestion["subject"], suggestion["suggested_task_due_date"]) == ("Owner interview", "2026-12-02")
    # Giriş yapılan oturum da listelenir.
    assert len(document["sessions"]) == 1
    assert "Other" not in response.text
    assert all("user_id" not in row for row in document["opportunities"])
    assert owner.id == document["account"]["id"]


def test_export_never_contains_authentication_secrets(authenticated_client, db_session):
    owner = db_session.query(User).filter_by(email="owner@example.com").one()

    response = authenticated_client.get("/auth/me/export")

    for secret_field in ("hashed_password", "token_hash", "family_id"):
        assert secret_field not in response.text
    assert owner.hashed_password not in response.text
    assert set(response.json()["sessions"][0]) == {"id", "persistent", "created_at", "expires_at", "revoked_at"}


def test_export_is_a_non_cached_download(authenticated_client):
    response = authenticated_client.get("/auth/me/export")

    assert response.headers["content-disposition"].startswith('attachment; filename="careertracker-verilerim-')
    assert response.headers["content-disposition"].endswith('.json"')
    assert response.headers["cache-control"] == "no-store"


def test_export_of_an_empty_account_has_empty_sections(authenticated_client):
    document = authenticated_client.get("/auth/me/export").json()

    assert document["opportunities"] == []
    assert document["email_suggestions"] == []
    assert document["account"]["email"] == "owner@example.com"


def test_export_requires_authentication(client):
    assert client.get("/auth/me/export").status_code == 401


def test_every_table_holding_user_data_is_exported():
    user_tables = {
        table.name
        for table in Base.metadata.tables.values()
        if {"user_id", "owner_user_id"} & set(table.columns.keys())
    }
    assert user_tables <= EXPORTED_TABLES
    assert EXPORTED_TABLES <= set(Base.metadata.tables)

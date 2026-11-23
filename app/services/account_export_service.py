"""Kullanıcının tüm kayıtlarını tek bir JSON belgesinde toplar (KVKK m.11, erişim hakkı).

Sütunlar model tanımından okunur; bir tabloya yeni sütun eklenince dışa aktarmaya da
kendiliğinden girer. Kimlik doğrulama sırları (şifre özeti, oturum ve sıfırlama token özetleri) asla
belgeye girmez.
"""

from datetime import date, datetime, timezone

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models.activities import Activity
from app.models.contacts import Contact
from app.models.email_insights import EmailSuggestion, InboundAddress
from app.models.opportunity import Opportunity
from app.models.opportunity_skills import OpportunitySkill
from app.models.password_reset_tokens import PasswordResetToken
from app.models.refresh_tokens import RefreshToken
from app.models.skills import PersonalSkillAlias, Skill, SkillSuggestion, UserSkill
from app.models.tasks import Task
from app.models.users import User

EXPORT_FORMAT_VERSION = 1

# Her bölüm: (belgedeki ad, model, kullanıcı sütunu, belgeye girmeyecek sütunlar)
_SECTIONS = (
    ("opportunities", Opportunity, Opportunity.user_id, ()),
    ("activities", Activity, Activity.user_id, ()),
    ("contacts", Contact, Contact.user_id, ()),
    ("tasks", Task, Task.user_id, ()),
    ("custom_skills", Skill, Skill.owner_user_id, ()),
    ("user_skills", UserSkill, UserSkill.user_id, ()),
    ("personal_skill_aliases", PersonalSkillAlias, PersonalSkillAlias.user_id, ()),
    ("skill_suggestions", SkillSuggestion, SkillSuggestion.user_id, ()),
    ("email_forwarding_addresses", InboundAddress, InboundAddress.user_id, ()),
    ("email_suggestions", EmailSuggestion, EmailSuggestion.user_id, ()),
    ("sessions", RefreshToken, RefreshToken.user_id, ("token_hash", "family_id")),
    ("password_reset_requests", PasswordResetToken, PasswordResetToken.user_id, ("token_hash",)),
)

# Kullanıcıya ait veri tutan tablolar; testler yeni bir tablonun unutulmadığını denetler.
EXPORTED_TABLES = frozenset(
    {User.__tablename__, OpportunitySkill.__tablename__}
    | {model.__tablename__ for _, model, _, _ in _SECTIONS}
)

_ALWAYS_EXCLUDED = frozenset({"user_id", "owner_user_id", "hashed_password"})


def _plain(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _row(record, excluded=()) -> dict:
    skipped = _ALWAYS_EXCLUDED | set(excluded)
    return {
        attribute.key: _plain(getattr(record, attribute.key))
        for attribute in inspect(record).mapper.column_attrs
        if attribute.key not in skipped
    }


def _skill_names(db: Session, skill_ids) -> dict[int, str]:
    ids = set(skill_ids)
    if not ids:
        return {}
    return dict(db.query(Skill.id, Skill.name).filter(Skill.id.in_(ids)).all())


def build_export(db: Session, user: User) -> dict:
    sections = {}
    for name, model, owner_column, excluded in _SECTIONS:
        records = db.query(model).filter(owner_column == user.id).order_by(model.id).all()
        sections[name] = [_row(record, excluded) for record in records]

    # Beceri kimlikleri tek başına anlamsız; okunabilirlik için adlarını da ekle.
    links = (
        db.query(OpportunitySkill)
        .join(Opportunity, OpportunitySkill.opportunity_id == Opportunity.id)
        .filter(Opportunity.user_id == user.id)
        .all()
    )
    names = _skill_names(
        db,
        [link.skill_id for link in links]
        + [row["skill_id"] for row in sections["user_skills"]]
        + [row["skill_id"] for row in sections["personal_skill_aliases"]],
    )
    skills_by_opportunity: dict[int, list[str]] = {}
    for link in links:
        skills_by_opportunity.setdefault(link.opportunity_id, []).append(names.get(link.skill_id))
    for opportunity in sections["opportunities"]:
        opportunity["skills"] = sorted(skills_by_opportunity.get(opportunity["id"], []))
    for row in sections["user_skills"] + sections["personal_skill_aliases"]:
        row["skill_name"] = names.get(row["skill_id"])

    return {
        "format_version": EXPORT_FORMAT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "account": _row(user),
        **sections,
    }

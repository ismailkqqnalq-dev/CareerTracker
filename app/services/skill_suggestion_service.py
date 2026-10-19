from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.skills import Skill, SkillSuggestion
from app.services.skill_normalizer import find_skill, normalize_text


def submit_suggestion(
    db: Session,
    *,
    user_id: int,
    raw_name: str,
) -> tuple[SkillSuggestion, bool]:
    normalized_name = normalize_text(raw_name)
    existing = (
        db.query(SkillSuggestion)
        .filter(
            SkillSuggestion.user_id == user_id,
            SkillSuggestion.normalized_name == normalized_name,
        )
        .first()
    )
    if existing is not None:
        return existing, False

    if find_skill(db, raw_name, user_id=user_id) is not None:
        raise ValueError(f"Skill is already recognized: {raw_name}")

    suggestion = SkillSuggestion(
        user_id=user_id,
        raw_name=raw_name.strip(),
        normalized_name=normalized_name,
        status="pending",
    )
    db.add(suggestion)
    try:
        db.commit()
        db.refresh(suggestion)
        return suggestion, True
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(SkillSuggestion)
            .filter(
                SkillSuggestion.user_id == user_id,
                SkillSuggestion.normalized_name == normalized_name,
            )
            .first()
        )
        if existing is None:
            raise
        return existing, False


def list_suggestions(
    db: Session,
    *,
    user_id: int,
    status: str | None = None,
) -> list[SkillSuggestion]:
    query = (
        db.query(SkillSuggestion)
        .filter(SkillSuggestion.user_id == user_id)
    )
    if status is not None:
        query = query.filter(SkillSuggestion.status == status)
    return query.order_by(SkillSuggestion.id).all()


def resolve_suggestion(
    db: Session,
    *,
    user_id: int,
    suggestion_id: int,
    skill_id: int,
) -> SkillSuggestion:
    suggestion = (
        db.query(SkillSuggestion)
        .filter(
            SkillSuggestion.id == suggestion_id,
            SkillSuggestion.user_id == user_id,
        )
        .first()
    )
    if suggestion is None:
        raise LookupError(f"Skill suggestion not found: {suggestion_id}")

    skill = db.get(Skill, skill_id)
    if skill is None:
        raise LookupError(f"Skill not found: {skill_id}")

    suggestion.resolved_skill_id = skill.id
    suggestion.status = "accepted"
    db.commit()
    db.refresh(suggestion)
    return suggestion

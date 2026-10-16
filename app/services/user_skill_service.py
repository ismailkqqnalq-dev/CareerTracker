from sqlalchemy.orm import Session

from app.models.skills import Skill, UserSkill


def add_skill(
    db: Session,
    user_id: int,
    skill_id: int,
    proficiency_level: str = "beginner",
    years_experience: float = 0.0,
) -> UserSkill:
    skill = db.get(Skill, skill_id)
    if skill is None:
        raise LookupError(f"Skill not found: {skill_id}")

    existing = (
        db.query(UserSkill)
        .filter(
            UserSkill.user_id == user_id,
            UserSkill.skill_id == skill_id,
        )
        .first()
    )
    if existing is not None:
        raise ValueError("Skill already exists in your profile")

    try:
        user_skill = UserSkill(
            user_id=user_id,
            skill_id=skill_id,
            proficiency_level=proficiency_level,
            years_experience=years_experience,
        )
        db.add(user_skill)
        db.commit()
        db.refresh(user_skill)
        return user_skill
    except Exception:
        db.rollback()
        raise


def list_skills(db: Session, user_id: int) -> list[UserSkill]:
    return (
        db.query(UserSkill)
        .filter(UserSkill.user_id == user_id)
        .order_by(UserSkill.id)
        .all()
    )
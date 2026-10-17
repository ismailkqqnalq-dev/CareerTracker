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
    
def update_skill(
    db: Session,
    user_id: int,
    user_skill_id: int,
    update_data: dict,
) -> UserSkill:
    user_skill = (
        db.query(UserSkill)
        .filter(
            UserSkill.id == user_skill_id,
            UserSkill.user_id == user_id,
        )
        .first()
    )
    if user_skill is None:
        raise LookupError(f"Profile skill not found: {user_skill_id}")

    if not update_data:
        raise ValueError("At least one field must be provided")

    try:
        for key, value in update_data.items():
            setattr(user_skill, key, value)

        db.commit()
        db.refresh(user_skill)
        return user_skill
    except Exception:
        db.rollback()
        raise


def delete_skill(
    db: Session,
    user_id: int,
    user_skill_id: int,
) -> None:
    user_skill = (
        db.query(UserSkill)
        .filter(
            UserSkill.id == user_skill_id,
            UserSkill.user_id == user_id,
        )
        .first()
    )
    if user_skill is None:
        raise LookupError(f"Profile skill not found: {user_skill_id}")

    try:
        db.delete(user_skill)
        db.commit()
    except Exception:
        db.rollback()
        raise
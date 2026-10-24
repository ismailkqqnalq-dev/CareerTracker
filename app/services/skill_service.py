from app.services.skill_normalizer import find_skill, normalize_text
from app.models.skills import Skill, SkillAliases, PersonalSkillAlias, SkillSuggestion
from app.services.skill_access import get_visible_skill
from sqlalchemy.exc import IntegrityError


def create_skill(db, name: str, category: str | None = None, *, user_id: int | None = None) -> Skill:
    if find_skill(db, name, user_id=user_id):
       raise ValueError(f"Skill already exists: {name}")
    try:
        skill = Skill(name=name.strip(), category=category, owner_user_id=user_id)
        db.add(skill)
        db.flush()
        
        alias = (SkillAliases(alias=normalize_text(name), skill_id=skill.id)
                 if user_id is None else
                 PersonalSkillAlias(user_id=user_id, alias=normalize_text(name), skill_id=skill.id))
        db.add(alias)
        db.commit()
        return skill
    except IntegrityError as error:
        db.rollback()
        raise ValueError(f'Skill already exists: {name}') from error
    except Exception :
        db.rollback()
        raise 

def add_alias(db, skill_id: int, alias: str, *, user_id: int) -> PersonalSkillAlias:
    skill = get_visible_skill(db, skill_id, user_id)
    if skill is None:
        raise LookupError(f"Skill not found: {skill_id}")

    normalized = normalize_text(alias)
    if not normalized:
        raise ValueError("Alias cannot be blank")

    existing = db.query(PersonalSkillAlias).filter(
        PersonalSkillAlias.user_id == user_id, PersonalSkillAlias.alias == normalized,
    ).first()
    accepted = db.query(SkillSuggestion).filter(
        SkillSuggestion.user_id == user_id,
        SkillSuggestion.normalized_name == normalized,
        SkillSuggestion.status == 'accepted',
    ).first()
    if existing is not None or accepted is not None:
        raise ValueError(f"Alias already exists: {normalized}")

    try:
        row = PersonalSkillAlias(user_id=user_id, alias=normalized, skill_id=skill_id)
        db.add(row)
        db.commit()
        return row
    except IntegrityError as error:
        db.rollback()
        raise ValueError(f'Alias already exists: {normalized}') from error
    except Exception:
        db.rollback()
        raise

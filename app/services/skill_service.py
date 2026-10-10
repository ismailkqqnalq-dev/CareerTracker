from app.services.skill_normalizer import find_skill, normalize_text
from app.models.skills import Skill, SkillAliases


def create_skill(db, name: str, category: str | None = None) -> Skill:
    if find_skill(db, name):
       raise ValueError(f"Skill already exists: {name}")
    try:
        skill = Skill(name=name.strip(), category=category)
        db.add(skill)
        db.flush()
        
        alias = SkillAliases(alias=normalize_text(name), skill_id=skill.id)
        db.add(alias)
        db.commit()
        return skill
    except Exception :
        db.rollback()
        raise 

def add_alias(db, skill_id: int, alias: str) -> SkillAliases:
    skill = db.get(Skill, skill_id)
    if skill is None:
        raise LookupError(f"Skill not found: {skill_id}")

    normalized = normalize_text(alias)
    if not normalized:
        raise ValueError("Alias cannot be blank")

    existing = db.query(SkillAliases).filter(SkillAliases.alias == normalized).first()
    if existing is not None:
        raise ValueError(f"Alias already exists: {normalized}")

    try:
        row = SkillAliases(alias=normalized, skill_id=skill_id)
        db.add(row)
        db.commit()
        return row
    except Exception:
        db.rollback()
        raise
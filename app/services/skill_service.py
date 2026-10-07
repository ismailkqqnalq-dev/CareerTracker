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
        
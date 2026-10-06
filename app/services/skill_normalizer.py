
from app.models.skills import Skill, SkillAliases


def normalize_text(text: str)-> str:
    return " ".join(text.split()).lower()

def find_skill(db, raw_text: str)-> Skill | None:
    normalized_text = normalize_text(raw_text)
    alias_row = db.query(SkillAliases).filter(SkillAliases.alias == normalized_text).first()
    if  alias_row is None:
        return None
    return db.get(Skill, alias_row.skill_id)
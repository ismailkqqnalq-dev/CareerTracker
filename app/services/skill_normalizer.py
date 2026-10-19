
from app.models.skills import Skill, SkillAliases, SkillSuggestion


def normalize_text(text: str)-> str:
    text = text.replace("İ", "i").replace("ı", "i")
    return " ".join(text.split()).lower()

def find_skill(db, raw_text: str, user_id: int | None = None) -> Skill | None:
    normalized_text = normalize_text(raw_text)

    if user_id is not None:
        user_suggestion = (
            db.query(SkillSuggestion)
            .filter(
                SkillSuggestion.user_id == user_id,
                SkillSuggestion.normalized_name == normalized_text,
                SkillSuggestion.status == "accepted",
                SkillSuggestion.resolved_skill_id.is_not(None),
            )
            .first()
        )
        if user_suggestion is not None:
            return db.get(Skill, user_suggestion.resolved_skill_id)

    alias_row = db.query(SkillAliases).filter(SkillAliases.alias == normalized_text).first()
    if  alias_row is None:
        return None
    return db.get(Skill, alias_row.skill_id)

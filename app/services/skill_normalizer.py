
from app.models.skills import Skill, SkillAliases, SkillSuggestion, PersonalSkillAlias
from app.services.skill_access import get_visible_skill


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
            return get_visible_skill(db, user_suggestion.resolved_skill_id, user_id)

        personal = db.query(PersonalSkillAlias).filter(
            PersonalSkillAlias.user_id == user_id,
            PersonalSkillAlias.alias == normalized_text,
        ).first()
        if personal is not None:
            return get_visible_skill(db, personal.skill_id, user_id)

    alias_row = db.query(SkillAliases).filter(SkillAliases.alias == normalized_text).first()
    if  alias_row is None:
        return None
    return get_visible_skill(db, alias_row.skill_id, user_id)

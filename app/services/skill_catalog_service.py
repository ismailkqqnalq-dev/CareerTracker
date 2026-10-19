from sqlalchemy.orm import Session

from app.models.skills import Skill, SkillAliases
from app.services.skill_normalizer import find_skill, normalize_text
from app.skill_catalog import SKILL_CATALOG


def seed_skill_catalog(db: Session) -> dict[str, int]:
    skills_created = 0
    aliases_created = 0
    pending_aliases: dict[str, int] = {}

    try:
        for entry in SKILL_CATALOG:
            name = entry["name"]

            # Önce kanonik adı, sonra mevcut alias kayıtlarını kontrol et.
            skill = (
                db.query(Skill)
                .filter(Skill.name == name)
                .first()
            )
            if skill is None:
                skill = find_skill(db, name)

            if skill is None:
                skill = Skill(
                    name=name,
                    category=entry["category"],
                )
                db.add(skill)
                db.flush()
                skills_created += 1
            elif skill.category is None:
                skill.category = entry["category"]

            for alias in (name, *entry["aliases"]):
                normalized = normalize_text(alias)

                pending_skill_id = pending_aliases.get(normalized)
                if pending_skill_id is not None:
                    if pending_skill_id != skill.id:
                        raise ValueError(
                            f"Catalog alias conflict: {normalized}"
                        )
                    continue

                existing = (
                    db.query(SkillAliases)
                    .filter(SkillAliases.alias == normalized)
                    .first()
                )
                if existing is not None:
                    if existing.skill_id != skill.id:
                        raise ValueError(
                            f"Alias '{normalized}' already belongs to "
                            f"another skill"
                        )
                    continue

                db.add(
                    SkillAliases(
                        alias=normalized,
                        skill_id=skill.id,
                    )
                )
                pending_aliases[normalized] = skill.id
                aliases_created += 1

        db.commit()
        return {
            "skills_created": skills_created,
            "aliases_created": aliases_created,
        }
    except Exception:
        db.rollback()
        raise
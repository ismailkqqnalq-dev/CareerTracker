from sqlalchemy import or_

from app.models.skills import Skill


def visible_skills(db, user_id: int | None = None):
    query = db.query(Skill)
    if user_id is None:
        return query.filter(Skill.owner_user_id.is_(None))
    return query.filter(or_(Skill.owner_user_id.is_(None), Skill.owner_user_id == user_id))


def get_visible_skill(db, skill_id: int, user_id: int | None = None):
    return visible_skills(db, user_id).filter(Skill.id == skill_id).first()

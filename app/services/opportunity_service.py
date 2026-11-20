from app.models.skills import Skill
from app.repositories import opportunity_repository as op
from app.record_limits import get_max_opportunities_per_user
from app.services.skill_access import visible_skills


class UnknownSkillIdsError(LookupError):
    pass


def create_opportunity(db, opportunity_data, user_id, skill_ids=()):
    skill_ids = list(dict.fromkeys(skill_ids))  # tekrarları at, sırayı koru
    if skill_ids:
        # Başka kullanıcının özel becerisi de "bilinmeyen" sayılır; varlığı sızdırılmaz.
        visible_ids = {
            skill_id
            for (skill_id,) in visible_skills(db, user_id)
            .with_entities(Skill.id)
            .filter(Skill.id.in_(skill_ids))
        }
        missing = [skill_id for skill_id in skill_ids if skill_id not in visible_ids]
        if missing:
            raise UnknownSkillIdsError(f"Unknown skill ids: {missing}")

    return op.create_opportunity(
        db,
        opportunity_data,
        user_id,
        max_per_user=get_max_opportunities_per_user(),
        skill_ids=skill_ids,
    )


def get_all_opportunities(db, user_id, limit=50, offset=0):
    return op.get_all_opportunities(db, user_id, limit, offset)


def iter_opportunities(db, user_id, batch_size=500):
    return op.iter_opportunities(db, user_id, batch_size)


def get_opportunity_by_id(db, opportunity_id, user_id):
    return op.get_opportunity_by_id(db, opportunity_id, user_id)


def update_opportunity(db, opportunity_id, update_data, user_id):
    return op.update_opportunity(db, opportunity_id, update_data, user_id)


def delete_opportunity(db, opportunity_id, user_id):
    return op.delete_opportunity(db, opportunity_id, user_id)


def get_dashboard_stats(db, user_id):
    return op.get_dashboard_stats(db, user_id)


def get_application_analytics(db, user_id, months):
    return op.get_application_analytics(db, user_id, months)

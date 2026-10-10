from app.models.opportunity import Opportunity
from app.models.opportunity_skills import OpportunitySkill
from app.models.skills import Skill
from app.services.skill_normalizer import find_skill


def _get_opportunity(db, opportunity_id: int) -> Opportunity:
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None:
        raise LookupError(f"Opportunity not found: {opportunity_id}")
    return opportunity


def attach_skill(db, opportunity_id: int, raw_skill: str) -> Skill:
    _get_opportunity(db, opportunity_id)

    skill = find_skill(db, raw_skill)
    if skill is None:
        raise LookupError(f"Unknown skill: {raw_skill}")

    if db.get(OpportunitySkill, (opportunity_id, skill.id)) is not None:
        raise ValueError(f"Skill already attached: {skill.name}")

    try:
        db.add(OpportunitySkill(opportunity_id=opportunity_id, skill_id=skill.id))
        db.commit()
        return skill
    except Exception:
        db.rollback()
        raise


def list_skills(db, opportunity_id: int) -> list[Skill]:
    _get_opportunity(db, opportunity_id)
    return (
        db.query(Skill)
        .join(OpportunitySkill, OpportunitySkill.skill_id == Skill.id)
        .filter(OpportunitySkill.opportunity_id == opportunity_id)
        .order_by(Skill.name)
        .all()
    )
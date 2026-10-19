from app.models.opportunity import Opportunity
from app.models.opportunity_skills import OpportunitySkill
from app.models.skills import Skill
from app.services.skill_normalizer import find_skill
from app.services.skill_suggestion_service import submit_suggestion


def _get_opportunity(db, opportunity_id: int, user_id: int) -> Opportunity:
    opportunity = (
        db.query(Opportunity)
        .filter(
            Opportunity.id == opportunity_id,
            Opportunity.user_id == user_id,
        )
        .first()
    )
    if opportunity is None:
        raise LookupError(f"Opportunity not found: {opportunity_id}")
    return opportunity


def attach_skill(
    db,
    opportunity_id: int,
    raw_skill: str,
    user_id: int,
) -> Skill:
    _get_opportunity(db, opportunity_id, user_id)

    skill = find_skill(db, raw_skill, user_id=user_id)
    if skill is None:
        submit_suggestion(db, user_id=user_id, raw_name=raw_skill)
        raise LookupError(
            f"Unknown skill: {raw_skill}. A suggestion was saved for review."
        )

    if db.get(OpportunitySkill, (opportunity_id, skill.id)) is not None:
        raise ValueError(f"Skill already attached: {skill.name}")

    try:
        db.add(
            OpportunitySkill(
                opportunity_id=opportunity_id,
                skill_id=skill.id,
            )
        )
        db.commit()
        return skill
    except Exception:
        db.rollback()
        raise


def list_skills(db, opportunity_id: int, user_id: int) -> list[Skill]:
    _get_opportunity(db, opportunity_id, user_id)

    return (
        db.query(Skill)
        .join(OpportunitySkill, OpportunitySkill.skill_id == Skill.id)
        .filter(OpportunitySkill.opportunity_id == opportunity_id)
        .order_by(Skill.name)
        .all()
    )

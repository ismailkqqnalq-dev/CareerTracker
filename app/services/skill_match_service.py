from sqlalchemy.orm import Session

from app.models.opportunity import Opportunity
from app.models.opportunity_skills import OpportunitySkill
from app.models.skills import Skill, UserSkill
from app.services.skill_access import visible_skills


def get_opportunity_skill_match(
    db: Session,
    opportunity_id: int,
    user_id: int,
) -> dict:
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

    required_skills = (
        visible_skills(db, user_id)
        .join(OpportunitySkill, OpportunitySkill.skill_id == Skill.id)
        .filter(OpportunitySkill.opportunity_id == opportunity_id)
        .order_by(Skill.name)
        .all()
    )

    profile_skill_ids = {
        skill_id
        for (skill_id,) in (
            db.query(UserSkill.skill_id)
            .filter(UserSkill.user_id == user_id)
            .all()
        )
    }

    matched_skills = [
        skill for skill in required_skills
        if skill.id in profile_skill_ids
    ]
    missing_skills = [
        skill for skill in required_skills
        if skill.id not in profile_skill_ids
    ]

    required_count = len(required_skills)
    matched_count = len(matched_skills)
    match_percentage = (
        round(matched_count / required_count * 100, 2)
        if required_count > 0
        else 0.0
    )

    return {
        "opportunity_id": opportunity_id,
        "required_skill_count": required_count,
        "matched_skill_count": matched_count,
        "match_percentage": match_percentage,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
    }

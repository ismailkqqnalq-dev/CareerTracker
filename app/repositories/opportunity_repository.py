from sqlalchemy import func

from app.models.opportunity import Opportunity


def create_opportunity(db, opportunity_data, user_id):
    new_opportunity = Opportunity(
        **opportunity_data,
        user_id=user_id,
    )
    db.add(new_opportunity)
    db.commit()
    db.refresh(new_opportunity)
    return new_opportunity


def get_all_opportunities(db, user_id):
    return (
        db.query(Opportunity)
        .filter(Opportunity.user_id == user_id)
        .all()
    )


def get_opportunity_by_id(db, opportunity_id, user_id):
    return (
        db.query(Opportunity)
        .filter(
            Opportunity.id == opportunity_id,
            Opportunity.user_id == user_id,
        )
        .first()
    )


def update_opportunity(db, opportunity_id, update_data, user_id):
    opportunity = get_opportunity_by_id(db, opportunity_id, user_id)
    if opportunity is None:
        return None

    for key, value in update_data.items():
        setattr(opportunity, key, value)

    db.commit()
    db.refresh(opportunity)
    return opportunity


def delete_opportunity(db, opportunity_id, user_id):
    opportunity = get_opportunity_by_id(db, opportunity_id, user_id)
    if opportunity is None:
        return False

    db.delete(opportunity)
    db.commit()
    return True


def get_dashboard_stats(db, user_id):
    user_filter = Opportunity.user_id == user_id

    total = (
        db.query(func.count(Opportunity.id))
        .filter(user_filter)
        .scalar()
        or 0
    )

    by_status = (
        db.query(Opportunity.status, func.count(Opportunity.id))
        .filter(user_filter)
        .group_by(Opportunity.status)
        .all()
    )

    by_company = (
        db.query(Opportunity.company, func.count(Opportunity.id))
        .filter(user_filter)
        .group_by(Opportunity.company)
        .all()
    )

    by_status_dict = dict(by_status)

    interview_count = (
        by_status_dict.get("Ön görüşme", 0)
        + by_status_dict.get("Teknik mülakat", 0)
        + by_status_dict.get("Son mülakat", 0)
    )
    offer_count = by_status_dict.get("Teklif", 0)
    rejected_count = by_status_dict.get("Reddedildi", 0)
    rejection_rate = rejected_count / total * 100 if total > 0 else 0

    return {
        "total_opportunities": total,
        "by_status": by_status_dict,
        "by_company": dict(by_company),
        "interview_count": interview_count,
        "offer_count": offer_count,
        "rejection_rate": round(rejection_rate, 2),
    }
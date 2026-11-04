from sqlalchemy import func

from app.models.opportunity import Opportunity
from app.pagination import paginate_query


def create_opportunity(db, opportunity_data, user_id):
    new_opportunity = Opportunity(
        **opportunity_data,
        user_id=user_id,
    )
    db.add(new_opportunity)
    db.commit()
    db.refresh(new_opportunity)
    return new_opportunity


def get_all_opportunities(db, user_id, limit=50, offset=0):
    return paginate_query(
        db.query(Opportunity).filter(Opportunity.user_id == user_id),
        order_by=Opportunity.id,
        limit=limit,
        offset=offset,
    )


def iter_opportunities(db, user_id, batch_size=500):
    return (
        db.query(Opportunity)
        .filter(Opportunity.user_id == user_id)
        .order_by(Opportunity.id)
        .yield_per(batch_size)
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
    normalized_status_counts = {}
    turkish_i_fold = str.maketrans({"İ": "i", "ı": "i"})
    for status, count in by_status:
        if status is not None:
            key = status.strip().translate(turkish_i_fold).casefold()
            normalized_status_counts[key] = normalized_status_counts.get(key, 0) + count

    interview_count = sum(
        normalized_status_counts.get(label.translate(turkish_i_fold).casefold(), 0)
        for label in ("Ön görüşme", "Teknik mülakat", "Son mülakat")
    )
    offer_count = normalized_status_counts.get("Teklif".casefold(), 0)
    rejected_count = normalized_status_counts.get("Reddedildi".casefold(), 0)
    rejection_rate = rejected_count / total * 100 if total > 0 else 0

    return {
        "total_opportunities": total,
        "by_status": by_status_dict,
        "by_company": dict(by_company),
        "interview_count": interview_count,
        "offer_count": offer_count,
        "rejection_rate": round(rejection_rate, 2),
    }

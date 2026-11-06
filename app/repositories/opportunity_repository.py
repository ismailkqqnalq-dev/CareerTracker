from datetime import date, datetime

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


def get_application_analytics(db, user_id, months):
    current_month = date.today().replace(day=1)
    current_index = current_month.year * 12 + current_month.month - 1
    start_index = current_index - months + 1
    start_year, start_month_index = divmod(start_index, 12)
    start_month = start_month_index + 1
    end_year, end_month_index = divmod(current_index + 1, 12)
    end_month = end_month_index + 1

    start_at = datetime(start_year, start_month, 1)
    end_at = datetime(end_year, end_month, 1)
    application_dates = (
        db.query(Opportunity.application_date)
        .filter(
            Opportunity.user_id == user_id,
            Opportunity.application_date >= start_at,
            Opportunity.application_date < end_at,
        )
        .all()
    )

    counts_by_month = {}
    for (application_date,) in application_dates:
        month_key = f"{application_date.year:04d}-{application_date.month:02d}"
        counts_by_month[month_key] = counts_by_month.get(month_key, 0) + 1

    monthly_counts = []
    for offset in range(months):
        month_index = start_index + offset
        year, month_index_zero_based = divmod(month_index, 12)
        month_key = f"{year:04d}-{month_index_zero_based + 1:02d}"
        monthly_counts.append(
            {"month": month_key, "count": counts_by_month.get(month_key, 0)}
        )

    return {
        "months": months,
        "start_month": monthly_counts[0]["month"],
        "end_month": monthly_counts[-1]["month"],
        "total_applications": sum(item["count"] for item in monthly_counts),
        "applications_by_month": monthly_counts,
    }

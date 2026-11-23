from datetime import date, datetime

from sqlalchemy import func, or_

from app.models.activities import Activity
from app.models.contacts import Contact
from app.models.opportunity import Opportunity
from app.models.opportunity_skills import OpportunitySkill
from app.models.skills import Skill
from app.models.tasks import Task
from app.models.users import User
from app.pagination import paginate_query
from app.record_limits import OpportunityQuotaExceeded


def create_opportunity(db, opportunity_data, user_id, max_per_user, skill_ids=()):
    # Serialize quota checks for one account on PostgreSQL, so simultaneous
    # requests cannot both pass the same count check.
    db.query(User.id).filter(User.id == user_id).with_for_update().one()
    current_count = (
        db.query(func.count(Opportunity.id))
        .filter(Opportunity.user_id == user_id)
        .scalar()
        or 0
    )
    if current_count >= max_per_user:
        db.rollback()
        raise OpportunityQuotaExceeded

    new_opportunity = Opportunity(
        **opportunity_data,
        user_id=user_id,
    )
    try:
        db.add(new_opportunity)
        db.flush()  # id'yi al; beceri bağlantıları aynı commit'te yazılsın
        for skill_id in skill_ids:
            db.add(OpportunitySkill(opportunity_id=new_opportunity.id, skill_id=skill_id))
        db.commit()
        db.refresh(new_opportunity)
    except Exception:
        db.rollback()
        raise
    return new_opportunity


# SQLite'ın lower() fonksiyonu yalnızca ASCII harfleri küçültür; "İstanbul"u "istanbul"
# ile bulmak için Türkçe harfler iki tarafta da aynı biçimde ASCII'ye katlanır.
# replace() ve lower() SQLite ile PostgreSQL'de aynı davranır.
_TURKISH_FOLD = (
    ("İ", "i"), ("I", "i"), ("ı", "i"),
    ("Ş", "s"), ("ş", "s"), ("Ğ", "g"), ("ğ", "g"),
    ("Ü", "u"), ("ü", "u"), ("Ö", "o"), ("ö", "o"), ("Ç", "c"), ("ç", "c"),
)
_SEARCH_COLUMNS = (
    Opportunity.company,
    Opportunity.position,
    Opportunity.type,
    Opportunity.location,
    Opportunity.next_action,
    Opportunity.notes,
)


def fold_search_text(value: str) -> str:
    for source, target in _TURKISH_FOLD:
        value = value.replace(source, target)
    return value.lower()


def _folded(column):
    expression = func.coalesce(column, "")
    for source, target in _TURKISH_FOLD:
        expression = func.replace(expression, source, target)
    return func.lower(expression)


def get_all_opportunities(db, user_id, limit=50, offset=0, search=None, status=None, newest_first=False):
    query = db.query(Opportunity).filter(Opportunity.user_id == user_id)
    if search:
        needle = fold_search_text(search)
        # autoescape: kullanıcının yazdığı % ve _ joker değil, düz karakter sayılır.
        query = query.filter(or_(*(_folded(column).contains(needle, autoescape=True) for column in _SEARCH_COLUMNS)))
    if status:
        query = query.filter(_folded(Opportunity.status) == fold_search_text(status))
    return paginate_query(
        query,
        order_by=Opportunity.id,
        limit=limit,
        offset=offset,
        newest_first=newest_first,
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


DETAIL_LIMIT = 200


def get_opportunity_detail(db, opportunity_id, user_id):
    """Başvuru ve bağlı kayıtları; her sorgu hem başvuruya hem kullanıcıya göre süzülür."""
    opportunity = get_opportunity_by_id(db, opportunity_id, user_id)
    if opportunity is None:
        return None

    def owned(model):
        return db.query(model).filter(model.user_id == user_id, model.opportunity_id == opportunity_id)

    return {
        "opportunity": opportunity,
        "contacts": owned(Contact).order_by(Contact.id).limit(DETAIL_LIMIT).all(),
        # Açık görevler önce, en yakın son tarih başta.
        "tasks": owned(Task)
        .order_by(Task.is_completed.is_(True), Task.due_date.is_(None), Task.due_date, Task.id)
        .limit(DETAIL_LIMIT)
        .all(),
        "activities": owned(Activity)
        .order_by(Activity.dates.is_(None), Activity.dates.desc(), Activity.id.desc())
        .limit(DETAIL_LIMIT)
        .all(),
        "skills": [
            {"id": skill_id, "name": name}
            for skill_id, name in db.query(Skill.id, Skill.name)
            .join(OpportunitySkill, OpportunitySkill.skill_id == Skill.id)
            .filter(OpportunitySkill.opportunity_id == opportunity_id)
            .order_by(Skill.name)
            .all()
        ],
    }


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

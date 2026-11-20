"""Genel bakış gündemi: yaklaşan/geciken açık görevler ve takip zamanı gelen başvurular."""

from datetime import date, datetime, time, timedelta

from sqlalchemy import or_

from app.models.opportunity import Opportunity
from app.models.tasks import Task

TASK_HORIZON_DAYS = 7
FOLLOW_UP_AFTER_DAYS = 7
MAX_ITEMS = 20

# Hâlâ yanıt beklenen aşamalar; Teklif ve Reddedildi takip gerektirmez.
ACTIVE_STATUSES = ("Başvuruldu", "Ön görüşme", "Teknik mülakat", "Son mülakat")
_TURKISH_I_FOLD = str.maketrans({"İ": "i", "ı": "i"})


def _status_key(status: str) -> str:
    return status.strip().translate(_TURKISH_I_FOLD).casefold()


_ACTIVE_KEYS = {_status_key(status) for status in ACTIVE_STATUSES}


def _as_date(value):
    return value.date() if isinstance(value, datetime) else value


def get_agenda(db, user_id: int, today: date) -> dict:
    horizon_end = datetime.combine(today + timedelta(days=TASK_HORIZON_DAYS), time.max)
    task_rows = (
        db.query(Task, Opportunity.company, Opportunity.position)
        .join(Opportunity, Task.opportunity_id == Opportunity.id)
        .filter(
            Task.user_id == user_id,
            Opportunity.user_id == user_id,
            or_(Task.is_completed.is_(False), Task.is_completed.is_(None)),
            Task.due_date.isnot(None),
            Task.due_date <= horizon_end,
        )
        .order_by(Task.due_date, Task.id)
        .limit(MAX_ITEMS)
        .all()
    )
    tasks = [
        {
            "id": task.id,
            "description": task.description,
            "due_date": _as_date(task.due_date),
            "opportunity_id": task.opportunity_id,
            "company": company,
            "position": position,
        }
        for task, company, position in task_rows
    ]

    cutoff = datetime.combine(today - timedelta(days=FOLLOW_UP_AFTER_DAYS), time.max)
    candidates = (
        db.query(Opportunity)
        .filter(
            Opportunity.user_id == user_id,
            or_(
                Opportunity.last_contact_date.is_(None),
                Opportunity.last_contact_date <= cutoff,
            ),
        )
        .all()
    )
    stale = [
        opportunity
        for opportunity in candidates
        if opportunity.status and _status_key(opportunity.status) in _ACTIVE_KEYS
    ]
    # Hiç iletişim tarihi olmayanlar önce, sonra en eski temas; veritabanının NULL sırasına bırakılmaz.
    stale.sort(key=lambda item: (item.last_contact_date is not None, item.last_contact_date or datetime.min, item.id))
    follow_ups = []
    for opportunity in stale[:MAX_ITEMS]:
        last_contact = _as_date(opportunity.last_contact_date)
        follow_ups.append({
            "id": opportunity.id,
            "company": opportunity.company,
            "position": opportunity.position,
            "status": opportunity.status,
            "last_contact_date": last_contact,
            "next_action": opportunity.next_action,
            "days_since_contact": (today - last_contact).days if last_contact else None,
        })

    return {"tasks": tasks, "follow_ups": follow_ups}

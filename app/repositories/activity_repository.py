from app.models.activities import Activity
from app.pagination import paginate_query


def create_activity(db, activity_data, user_id):
    data = {**activity_data, "user_id": user_id}
    activity = Activity(**data)

    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


def get_all_activities(db, user_id, limit=50, offset=0):
    return paginate_query(
        db.query(Activity).filter(Activity.user_id == user_id),
        order_by=Activity.id,
        limit=limit,
        offset=offset,
    )


def get_activity_by_id(db, activity_id, user_id):
    return (
        db.query(Activity)
        .filter(
            Activity.id == activity_id,
            Activity.user_id == user_id,
        )
        .first()
    )


def update_activity(db, activity_id, activity_data, user_id):
    activity = get_activity_by_id(db, activity_id, user_id)
    if activity is None:
        return None

    for key, value in activity_data.items():
        setattr(activity, key, value)

    db.commit()
    db.refresh(activity)
    return activity


def delete_activity(db, activity_id, user_id):
    activity = get_activity_by_id(db, activity_id, user_id)
    if activity is None:
        return False

    db.delete(activity)
    db.commit()
    return True

from app.repositories import opportunity_repository as op
from app.repositories import task_repository as tr


def _require_owned_opportunity(db, opportunity_id, user_id):
    if opportunity_id is None:
        raise ValueError("Opportunity ID cannot be null")

    opportunity = op.get_opportunity_by_id(
        db,
        opportunity_id,
        user_id=user_id,
    )
    if opportunity is None:
        raise LookupError("Opportunity not found")

    return opportunity


def create_task(db, task_data, user_id):
    _require_owned_opportunity(
        db,
        task_data.get("opportunity_id"),
        user_id,
    )
    return tr.create_task(db, task_data, user_id=user_id)


def get_all_tasks(db, user_id):
    return tr.get_all_tasks(db, user_id=user_id)


def get_task_by_id(db, task_id, user_id):
    return tr.get_task_by_id(db, task_id, user_id=user_id)


def update_task(db, task_id, update_data, user_id):
    task = tr.get_task_by_id(db, task_id, user_id=user_id)
    if task is None:
        raise LookupError("Task not found")

    if "opportunity_id" in update_data:
        _require_owned_opportunity(
            db,
            update_data["opportunity_id"],
            user_id,
        )

    return tr.update_task(
        db,
        task_id,
        update_data,
        user_id=user_id,
    )


def delete_task(db, task_id, user_id):
    return tr.delete_task(db, task_id, user_id=user_id)
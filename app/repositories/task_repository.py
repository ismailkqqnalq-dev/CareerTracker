from app.models.tasks import Task


def create_task(db, task_data, user_id):
    data = {**task_data, "user_id": user_id}
    task = Task(**data)

    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_all_tasks(db, user_id):
    return (
        db.query(Task)
        .filter(Task.user_id == user_id)
        .all()
    )


def get_task_by_id(db, task_id, user_id):
    return (
        db.query(Task)
        .filter(
            Task.id == task_id,
            Task.user_id == user_id,
        )
        .first()
    )


def update_task(db, task_id, update_data, user_id):
    task = get_task_by_id(db, task_id, user_id)
    if task is None:
        return None

    for key, value in update_data.items():
        setattr(task, key, value)

    db.commit()
    db.refresh(task)
    return task


def delete_task(db, task_id, user_id):
    task = get_task_by_id(db, task_id, user_id)
    if task is None:
        return False

    db.delete(task)
    db.commit()
    return True
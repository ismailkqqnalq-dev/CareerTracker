from app.repositories import task_repository as tr

def create_task(db, task_data):
    return tr.create_task(db, task_data)

def get_all_tasks(db):
    return tr.get_all_tasks(db)

def get_task_by_id(db, task_id):
    return tr.get_task_by_id(db, task_id)

def update_task(db, task_id, update_data):
    return tr.update_task(db, task_id, update_data)

def delete_task(db, task_id):
    return tr.delete_task(db, task_id)
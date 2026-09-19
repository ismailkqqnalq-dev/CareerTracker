from sqlalchemy.orm import Session
from app.models.tasks import Task

def create_task(db, task_data):
    new_task = Task(**task_data)
    db.add(new_task)
    db.commit()
    return new_task

def get_all_tasks(db):
    return db.query(Task).all()

def get_task_by_id(db, task_id):
    return db.query(Task).filter(Task.id == task_id).first()
    
def update_task(db, task_id, update_data):
    task= db.query(Task).filter(Task.id==task_id).first()
    if task:
        for key,value in update_data.items():
            setattr(task,key,value)
        db.commit()
        db.refresh(task)
        return task
    return None
def delete_task(db, task_id):
    task= db.query(Task).filter(Task.id==task_id).first()
    if task:
        db.delete(task)
        db.commit()
        return True
    return False
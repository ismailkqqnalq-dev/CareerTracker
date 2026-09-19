from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models import tasks
from app.services import task_service as tasks
from app.schemas.tasks import TaskCreate, TaskResponse, TaskUpdate
router=APIRouter()
@router.post("/tasks", response_model=TaskResponse)
def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    result = tasks.create_task(db, task.model_dump())
    return result

@router.get("/tasks", response_model=list[TaskResponse])
def get_all_tasks(db: Session = Depends(get_db)):
    return tasks.get_all_tasks(db)

@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: int,  db: Session= Depends(get_db)):
    task = tasks.get_task_by_id(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.patch("/tasks/{task_id}", response_model= TaskResponse)
def update_task(task_id:int, update_data: TaskUpdate, db: Session = Depends(get_db)):
    updated_task= tasks.update_task(db, task_id, update_data.model_dump(exclude_unset=True))
    return updated_task

@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    result = tasks.delete_task(db, task_id)
    if result:
        return {"message": "Task deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Task not found")
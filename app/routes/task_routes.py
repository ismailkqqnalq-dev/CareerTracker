from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database.session import get_db
from app.models.users import User
from app.pagination import pagination_params, set_total_count
from app.schemas.tasks import TaskCreate, TaskResponse, TaskUpdate
from app.services import task_service as service


router = APIRouter()


@router.post("/tasks", response_model=TaskResponse)
def create_task(
    task: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return service.create_task(
            db,
            task.model_dump(),
            user_id=current_user.id,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))


@router.get("/tasks", response_model=list[TaskResponse])
def get_all_tasks(
    response: Response,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = service.get_all_tasks(
        db, user_id=current_user.id, limit=pagination[0], offset=pagination[1]
    )
    set_total_count(response, total)
    return items


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = service.get_task_by_id(
        db,
        task_id,
        user_id=current_user.id,
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    update_data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        task = service.update_task(
            db,
            task_id,
            update_data.model_dump(exclude_unset=True),
            user_id=current_user.id,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = service.delete_task(
        db,
        task_id,
        user_id=current_user.id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    return {"message": "Task deleted successfully"}

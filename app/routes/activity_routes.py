from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database.session import get_db
from app.models.users import User
from app.schemas.activities import (
    ActivityCreate,
    ActivityResponse,
    ActivityUpdate,
)
from app.services import activity_service as service


router = APIRouter()


@router.post("/activities", response_model=ActivityResponse)
def create_activity(
    activity: ActivityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return service.create_activity(
            db,
            activity.model_dump(),
            user_id=current_user.id,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))


@router.get("/activities", response_model=list[ActivityResponse])
def get_all_activities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_all_activities(db, user_id=current_user.id)


@router.get("/activities/{activity_id:int}", response_model=ActivityResponse)
def get_activity_by_id(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    activity = service.get_activity_by_id(
        db,
        activity_id,
        user_id=current_user.id,
    )
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")

    return activity


@router.patch("/activities/{activity_id:int}", response_model=ActivityResponse)
def update_activity(
    activity_id: int,
    update_data: ActivityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        activity = service.update_activity(
            db,
            activity_id,
            update_data.model_dump(exclude_unset=True),
            user_id=current_user.id,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))

    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")

    return activity


@router.delete("/activities/{activity_id:int}", response_model=dict)
def delete_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = service.delete_activity(
        db,
        activity_id,
        user_id=current_user.id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Activity not found")

    return {"message": "Activity deleted successfully"}
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models import activities
from app.services import activity_service as service
from app.schemas.activities import ActivityCreate, ActivityResponse, ActivityUpdate
router = APIRouter()
@router.post("/activities", response_model=ActivityResponse)
def create_activity(activity: ActivityCreate, db: Session =Depends(get_db)):
    result= service.create_activity(db, activity.model_dump())    
    return result

@router.get("/activities", response_model=list[ActivityResponse])
def get_all_activities(db: Session = Depends(get_db)):
    return service.get_all_activities(db)

@router.get("/activities/{activity_id:int}", response_model=ActivityResponse)
def get_activity_by_id(activity_id: int, db: Session = Depends(get_db)):
    activity= service.get_activity_by_id(db, activity_id)
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity

@router.patch("/activities/{activity_id:int}", response_model=ActivityResponse)
def update_activity(activity_id: int, update_data: ActivityUpdate, db: Session = Depends(get_db)):
    updated_activity = service.update_activity(
        db, activity_id, update_data.model_dump(exclude_unset=True)
    )
    return updated_activity

@router.delete("/activities/{activity_id:int}", response_model=dict)
def delete_activity(activity_id: int, db: Session = Depends(get_db)):
    result = service.delete_activity(db, activity_id)
    if result:
        return {"message": "Activity deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Activity not found")
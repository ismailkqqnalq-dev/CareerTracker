from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.skills import SkillCreate, SkillResponse
from app.services import skill_service as service
from app.services.skill_normalizer import find_skill

router = APIRouter()


@router.post("/skills", response_model=SkillResponse, status_code=201)
def create_skill(skill_data: SkillCreate, db: Session = Depends(get_db)):
    try:
        return service.create_skill(
            db,
            name=skill_data.name,
            category=skill_data.category,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))


@router.get("/skills/resolve", response_model=SkillResponse)
def resolve_skill(
    name: str = Query(min_length=1),
    db: Session = Depends(get_db),
):
    skill = find_skill(db, name)
    
    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill not found: {name}")
    return skill
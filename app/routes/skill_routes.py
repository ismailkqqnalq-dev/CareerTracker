from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db

from app.services import skill_service as service
from app.services.skill_normalizer import find_skill
from app.schemas.skills import (
    AliasCreate,
    AliasResponse,
    OpportunitySkillAdd,
    SkillCreate,
    SkillResponse,
)
from app.services import opportunity_skill_service
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

@router.post("/skills/{skill_id}/aliases", response_model=AliasResponse, status_code=201)
def add_alias(skill_id: int, data: AliasCreate, db: Session = Depends(get_db)):
    try:
        return service.add_alias(db, skill_id, data.alias)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))


@router.post(
    "/opportunities/{opportunity_id}/skills",
    response_model=SkillResponse,
    status_code=201,
)
def attach_skill(opportunity_id: int, data: OpportunitySkillAdd, db: Session = Depends(get_db)):
    try:
        return opportunity_skill_service.attach_skill(db, opportunity_id, data.skill)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))


@router.get("/opportunities/{opportunity_id}/skills", response_model=list[SkillResponse])
def list_opportunity_skills(opportunity_id: int, db: Session = Depends(get_db)):
    try:
        return opportunity_skill_service.list_skills(db, opportunity_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
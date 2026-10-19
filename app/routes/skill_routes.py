from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.services import skill_match_service
from app.services import skill_service as service
from app.services.skill_normalizer import find_skill
from app.services import opportunity_skill_service
from app.services import user_skill_service

from app.schemas.skills import (
    AliasCreate,
    AliasResponse,
    OpportunitySkillAdd,
    SkillCreate,
    SkillResponse,
    UserSkillUpdate,
    SkillMatchResponse,
)

from app.auth import get_current_user
from app.models.users import User

from app.schemas.skills import UserSkillCreate, UserSkillResponse

router = APIRouter()


@router.post(
    "/skills",
    response_model=SkillResponse,
    status_code=201,
    dependencies=[Depends(get_current_user)],
)
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

@router.post(
    "/skills/{skill_id}/aliases",
    response_model=AliasResponse,
    status_code=201,
    dependencies=[Depends(get_current_user)],
)
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
def attach_skill(
    opportunity_id: int,
    data: OpportunitySkillAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return opportunity_skill_service.attach_skill(
            db,
            opportunity_id,
            data.skill,
            user_id=current_user.id,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))


@router.get(
    "/opportunities/{opportunity_id}/skills",
    response_model=list[SkillResponse],
)
def list_opportunity_skills(
    opportunity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return opportunity_skill_service.list_skills(
            db,
            opportunity_id,
            user_id=current_user.id,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    
@router.post(
    "/users/me/skills",
    response_model=UserSkillResponse,
    status_code=201,
)
def add_profile_skill(
    data: UserSkillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return user_skill_service.add_skill(
            db,
            user_id=current_user.id,
            skill_id=data.skill_id,
            proficiency_level=data.proficiency_level,
            years_experience=data.years_experience,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))


@router.get(
    "/users/me/skills",
    response_model=list[UserSkillResponse],
)
def list_profile_skills(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return user_skill_service.list_skills(
        db,
        user_id=current_user.id,
    )
    
@router.patch(
    "/users/me/skills/{user_skill_id}",
    response_model=UserSkillResponse,
)
def update_profile_skill(
    user_skill_id: int,
    data: UserSkillUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return user_skill_service.update_skill(
            db,
            user_id=current_user.id,
            user_skill_id=user_skill_id,
            update_data=data.model_dump(exclude_unset=True),
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))


@router.delete("/users/me/skills/{user_skill_id}")
def delete_profile_skill(
    user_skill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        user_skill_service.delete_skill(
            db,
            user_id=current_user.id,
            user_skill_id=user_skill_id,
        )
        return {"message": "Profile skill deleted successfully"}
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    
@router.get(
    "/opportunities/{opportunity_id}/skill-match",
    response_model=SkillMatchResponse,
)
def get_opportunity_skill_match(
    opportunity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return skill_match_service.get_opportunity_skill_match(
            db,
            opportunity_id=opportunity_id,
            user_id=current_user.id,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
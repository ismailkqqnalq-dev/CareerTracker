from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.skills import Skill
from app.services import skill_match_service
from app.services import skill_service as service
from app.services.skill_normalizer import find_skill
from app.services import opportunity_skill_service
from app.services import user_skill_service
from app.services import skill_suggestion_service
from app.services.skill_access import visible_skills

from app.schemas.skills import (
    AliasCreate,
    AliasResponse,
    OpportunitySkillAdd,
    SkillCreate,
    SkillResponse,
    UserSkillUpdate,
    SkillMatchResponse,
    SkillSuggestionCreate,
    SkillSuggestionResponse,
    SkillSuggestionResolve,
    SkillSuggestionCandidate,
)

from app.auth import get_current_user, get_optional_current_user
from app.models.users import User

from app.schemas.skills import UserSkillCreate, UserSkillResponse

router = APIRouter()


@router.get("/skills", response_model=list[SkillResponse])
def list_skills(db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_current_user)):
    return visible_skills(db, current_user.id if current_user else None).order_by(Skill.name, Skill.id).all()


@router.post(
    "/skills/suggestions",
    response_model=SkillSuggestionResponse,
    status_code=201,
)
def submit_skill_suggestion(
    data: SkillSuggestionCreate,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        suggestion, created = skill_suggestion_service.submit_suggestion(
            db,
            user_id=current_user.id,
            raw_name=data.skill,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))
    if not created:
        # Returning an existing suggestion makes repeated submissions safe.
        response.status_code = 200
    return suggestion


@router.get(
    "/skills/suggestions",
    response_model=list[SkillSuggestionResponse],
)
def list_skill_suggestions(
    status: str | None = Query(default=None, pattern="^(pending|accepted|rejected)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return skill_suggestion_service.list_suggestions(
        db,
        user_id=current_user.id,
        status=status,
    )


@router.patch(
    "/skills/suggestions/{suggestion_id}",
    response_model=SkillSuggestionResponse,
)
def resolve_skill_suggestion(
    suggestion_id: int,
    data: SkillSuggestionResolve,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return skill_suggestion_service.resolve_suggestion(
            db,
            user_id=current_user.id,
            suggestion_id=suggestion_id,
            skill_id=data.skill_id,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.get(
    "/skills/suggestions/{suggestion_id}/candidates",
    response_model=list[SkillSuggestionCandidate],
)
def get_skill_suggestion_candidates(
    suggestion_id: int,
    limit: int = Query(default=5, ge=1, le=10),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        candidates = skill_suggestion_service.rank_skill_candidates(
            db,
            user_id=current_user.id,
            suggestion_id=suggestion_id,
            limit=limit,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))

    return [
        SkillSuggestionCandidate(
            id=skill.id,
            name=skill.name,
            category=skill.category,
            score=score,
        )
        for skill, score in candidates
    ]


@router.post(
    "/skills",
    response_model=SkillResponse,
    status_code=201,
)
def create_skill(skill_data: SkillCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return service.create_skill(
            db,
            name=skill_data.name,
            category=skill_data.category,
            user_id=current_user.id,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))


@router.get("/skills/resolve", response_model=SkillResponse)
def resolve_skill(
    name: str = Query(min_length=1),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    skill = find_skill(
        db,
        name,
        user_id=current_user.id if current_user is not None else None,
    )
    
    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill not found: {name}")
    return skill

@router.post(
    "/skills/{skill_id}/aliases",
    response_model=AliasResponse,
    status_code=201,
)
def add_alias(skill_id: int, data: AliasCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return service.add_alias(db, skill_id, data.alias, user_id=current_user.id)
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

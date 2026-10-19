from datetime import datetime
from typing import Annotated, Optional, Literal
from pydantic import BaseModel, ConfigDict, StringConstraints, Field, field_validator


class SkillBase(BaseModel):
    name: Annotated[str,StringConstraints(strip_whitespace=True, min_length=1)]
    category: Optional[str]= None 
    

class SkillCreate(SkillBase):
    pass


class SkillResponse(SkillBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
   
class AliasCreate(BaseModel):
    alias: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AliasResponse(BaseModel):
    id: int
    alias: str
    skill_id: int
    model_config = ConfigDict(from_attributes=True)


class OpportunitySkillAdd(BaseModel):
    skill: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    



class UserSkillCreate(BaseModel):
    skill_id: int = Field(gt=0)
    proficiency_level: Literal[
        "beginner",
        "intermediate",
        "advanced",
        "expert",
    ] = "beginner"
    years_experience: float = Field(default=0, ge=0)


class UserSkillResponse(BaseModel):
    id: int
    skill_id: int
    proficiency_level: Literal[
        "beginner",
        "intermediate",
        "advanced",
        "expert",
    ]
    years_experience: float

    model_config = ConfigDict(from_attributes=True)
    
class UserSkillUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proficiency_level: Literal[
        "beginner",
        "intermediate",
        "advanced",
        "expert",
    ] | None = None

    years_experience: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )

    @field_validator("proficiency_level", "years_experience")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Field cannot be null")
        return value
    
class SkillMatchResponse(BaseModel):
    opportunity_id: int
    required_skill_count: int
    matched_skill_count: int
    match_percentage: float
    matched_skills: list[SkillResponse]
    missing_skills: list[SkillResponse]


class SkillSuggestionCreate(BaseModel):
    skill: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
    ]


class SkillSuggestionResponse(BaseModel):
    id: int
    raw_name: str
    normalized_name: str
    resolved_skill_id: int | None
    status: Literal["pending", "accepted", "rejected"]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SkillSuggestionResolve(BaseModel):
    skill_id: int = Field(gt=0)

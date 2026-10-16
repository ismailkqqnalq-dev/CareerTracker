from typing import Annotated, Optional, Literal
from pydantic import BaseModel, ConfigDict, StringConstraints, Field


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
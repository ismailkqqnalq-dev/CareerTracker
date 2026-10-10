from typing import Annotated, Optional
from pydantic import BaseModel, ConfigDict, StringConstraints

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
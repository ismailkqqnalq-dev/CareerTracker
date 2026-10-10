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
   

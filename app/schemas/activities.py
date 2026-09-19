from pydantic import BaseModel
from datetime import date
from typing import Optional

class ActivityBase(BaseModel):
    opportunity_id: int
    contact_id: Optional[int] = None
    activity_type: str
    dates: date
    notes: str
    
class ActivityCreate(ActivityBase):
    pass

class ActivityResponse(ActivityBase):
    id: int
    
    class Config:
        from_attributes = True

class ActivityUpdate(BaseModel):
    opportunity_id:Optional[int]=None
    contact_id: Optional[int]= None
    activity_type: Optional[str]=None
    dates: Optional[date]=None
    notes: Optional[str]=None
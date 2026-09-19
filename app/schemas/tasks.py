from pydantic import BaseModel
from datetime import date
from typing import Optional

class TaskBase(BaseModel):
    
    opportunity_id: int
    description: str
    due_date: date
    is_completed:bool=False
    
class TaskCreate(TaskBase):
    pass

class TaskResponse(TaskBase):
    id: int 
    class Config:
        from_attributes = True
        
class TaskUpdate(BaseModel):
    opportunity_id:Optional[int]=None
    description: Optional[str]=None
    due_date: Optional[date]=None
    is_completed: Optional[bool] = None
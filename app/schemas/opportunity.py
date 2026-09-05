from pydantic import BaseModel
from datetime import date
from typing import Optional
class OpportunityBase(BaseModel):
     
        company:str
        position:str
        type:str
        application_date:date
        job_link:str
        salary:int
        location:str
        status:str
        notes:str
        next_action:str
        last_contact_date:date
class OpportunityCreate(OpportunityBase):
    pass
class OpportunityResponse(OpportunityBase):
    id:int
    class ConfigDict:
        from_attributes = True
    
class OpportunityUpdate(BaseModel):
    class OpportunityUpdate(BaseModel):
        company : Optional[str] = None,
        position : Optional[str] = None,
        type : Optional[str] = None,
        application_date : Optional[date] = None,
        job_link : Optional[str] = None,
        salary : Optional[int] = None,
        location : Optional[str] = None,
        status : Optional[str] = None,
        notes : Optional[str] = None,
        next_action : Optional[str] = None,
        last_contact_date : Optional[date] = None
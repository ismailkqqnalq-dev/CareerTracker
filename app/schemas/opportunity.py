from pydantic import BaseModel
from datetime import date
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
    class Config:
        from_attributes = True
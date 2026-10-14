from pydantic import BaseModel, ConfigDict
from typing import Optional

class ContactBase(BaseModel):
    name: str
    role: str
    email: str
    linkedin: str
    opportunity_id: int

class ContactCreate(ContactBase):
    pass

class ContactResponse(ContactBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
        
class ContactUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    linkedin: Optional[str] = None
    opportunity_id: Optional[int] = None

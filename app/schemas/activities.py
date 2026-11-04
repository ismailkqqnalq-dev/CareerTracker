from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


ActivityType = Annotated[str, StringConstraints(max_length=100)]
Notes = Annotated[str, StringConstraints(max_length=5000)]


class ActivityCreate(BaseModel):
    opportunity_id: int
    contact_id: int | None = None
    activity_type: ActivityType
    dates: date
    notes: Notes


class ActivityResponse(BaseModel):
    opportunity_id: int
    contact_id: int | None
    activity_type: str | None
    dates: date | None
    notes: str | None
    id: int

    model_config = ConfigDict(from_attributes=True)


class ActivityUpdate(BaseModel):
    opportunity_id: int | None = None
    contact_id: int | None = None
    activity_type: ActivityType | None = None
    dates: date | None = None
    notes: Notes | None = None

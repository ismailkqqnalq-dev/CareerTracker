from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


Description = Annotated[str, StringConstraints(max_length=2000)]


class TaskCreate(BaseModel):
    opportunity_id: int
    description: Description
    due_date: date
    is_completed: bool = False


class TaskResponse(BaseModel):
    opportunity_id: int
    description: str | None
    due_date: date | None
    is_completed: bool | None
    id: int

    model_config = ConfigDict(from_attributes=True)


class TaskUpdate(BaseModel):
    opportunity_id: int | None = None
    description: Description | None = None
    due_date: date | None = None
    is_completed: bool | None = None

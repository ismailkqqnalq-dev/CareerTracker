from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.schemas.validators import validate_http_url


Company = Annotated[str, StringConstraints(max_length=200)]
Position = Annotated[str, StringConstraints(max_length=200)]
OpportunityType = Annotated[str, StringConstraints(max_length=50)]
JobLink = Annotated[str, StringConstraints(max_length=2048)]
Location = Annotated[str, StringConstraints(max_length=200)]
Status = Annotated[str, StringConstraints(max_length=50)]
Notes = Annotated[str, StringConstraints(max_length=5000)]
NextAction = Annotated[str, StringConstraints(max_length=500)]
Salary = Annotated[int, Field(ge=0, le=2_147_483_647)]


class OpportunityCreate(BaseModel):
    company: Company
    position: Position
    type: OpportunityType
    application_date: date
    job_link: JobLink
    salary: Salary
    location: Location
    status: Status
    notes: Notes
    next_action: NextAction
    last_contact_date: date

    @field_validator("job_link")
    @classmethod
    def validate_job_link(cls, value: str) -> str:
        return validate_http_url(value)


class OpportunityResponse(BaseModel):
    company: str | None
    position: str | None
    type: str | None
    application_date: date | None
    job_link: str | None
    salary: int | None
    location: str | None
    status: str | None
    notes: str | None
    next_action: str | None
    last_contact_date: date | None
    id: int

    model_config = ConfigDict(from_attributes=True)


class OpportunityUpdate(BaseModel):
    company: Company | None = None
    position: Position | None = None
    type: OpportunityType | None = None
    application_date: date | None = None
    job_link: JobLink | None = None
    salary: Salary | None = None
    location: Location | None = None
    status: Status | None = None
    notes: Notes | None = None
    next_action: NextAction | None = None
    last_contact_date: date | None = None

    @field_validator("job_link")
    @classmethod
    def validate_job_link(cls, value: str | None) -> str | None:
        return validate_http_url(value)

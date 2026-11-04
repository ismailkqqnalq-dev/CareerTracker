from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from app.schemas.validators import validate_http_url


Name = Annotated[str, StringConstraints(max_length=200)]
Role = Annotated[str, StringConstraints(max_length=200)]
Email = Annotated[str, StringConstraints(max_length=320)]
LinkedIn = Annotated[str, StringConstraints(max_length=2048)]


class ContactCreate(BaseModel):
    name: Name
    role: Role
    email: Email
    linkedin: LinkedIn
    opportunity_id: int

    @field_validator("linkedin")
    @classmethod
    def validate_linkedin(cls, value: str) -> str:
        return validate_http_url(value)


class ContactResponse(BaseModel):
    name: str | None
    role: str | None
    email: str | None
    linkedin: str | None
    opportunity_id: int | None
    id: int

    model_config = ConfigDict(from_attributes=True)


class ContactUpdate(BaseModel):
    name: Name | None = None
    role: Role | None = None
    email: Email | None = None
    linkedin: LinkedIn | None = None
    opportunity_id: int | None = None

    @field_validator("linkedin")
    @classmethod
    def validate_linkedin(cls, value: str | None) -> str | None:
        return validate_http_url(value)

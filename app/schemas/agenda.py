from datetime import date

from pydantic import BaseModel


class AgendaTask(BaseModel):
    id: int
    description: str | None
    due_date: date
    opportunity_id: int
    company: str | None
    position: str | None


class AgendaFollowUp(BaseModel):
    id: int
    company: str | None
    position: str | None
    status: str | None
    last_contact_date: date | None
    next_action: str | None
    days_since_contact: int | None


class AgendaResponse(BaseModel):
    tasks: list[AgendaTask]
    follow_ups: list[AgendaFollowUp]

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AssistantQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=500)
    today: date | None = None

    @field_validator("message")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message cannot be blank")
        return value.strip()


class AssistantItem(BaseModel):
    title: str
    details: list[str]


class AssistantReply(BaseModel):
    intent: str
    confidence: float
    reply: str
    items: list[AssistantItem]
    suggestions: list[str]

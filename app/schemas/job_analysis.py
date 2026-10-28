from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class JobTextAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=100_000)


class JobTextOccurrence(BaseModel):
    line_number: int = Field(ge=1)
    matched_text: str
    section: Literal["required", "preferred", "unspecified"]


class JobTextSkill(BaseModel):
    skill_id: int
    name: str
    category: str | None
    occurrences: list[JobTextOccurrence]


class JobTextAnalysisResponse(BaseModel):
    role: str | None
    skills: list[JobTextSkill]

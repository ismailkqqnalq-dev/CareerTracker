from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class JobTextAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=100_000)


class JobTextOccurrence(BaseModel):
    line_number: int = Field(ge=1)
    matched_text: str
    section: Literal["required", "preferred", "unspecified"]


class JobTextMetadataValue(BaseModel):
    value: str
    line_number: int = Field(ge=1)


class JobTextMetadata(BaseModel):
    company: JobTextMetadataValue | None = None
    location: JobTextMetadataValue | None = None
    employment_type: JobTextMetadataValue | None = None
    work_arrangement: JobTextMetadataValue | None = None
    salary: JobTextMetadataValue | None = None
    experience: JobTextMetadataValue | None = None
    education: JobTextMetadataValue | None = None
    application_url: JobTextMetadataValue | None = None


class JobTextSkill(BaseModel):
    skill_id: int
    name: str
    category: str | None
    occurrences: list[JobTextOccurrence]
    profile_status: Literal["in_profile", "missing"]
    profile_proficiency_level: Literal[
        "beginner", "intermediate", "advanced", "expert"
    ] | None
    profile_years_experience: float | None


class JobTextSectionMatch(BaseModel):
    total_count: int
    matched_count: int
    match_percentage: float | None
    missing_skills: list[str]


class JobTextProfileMatch(BaseModel):
    required: JobTextSectionMatch
    preferred: JobTextSectionMatch
    unspecified: JobTextSectionMatch


class JobTextAnalysisResponse(BaseModel):
    role: str | None
    role_line_number: int | None
    metadata: JobTextMetadata
    skills: list[JobTextSkill]
    profile_match: JobTextProfileMatch

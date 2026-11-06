from pydantic import BaseModel, Field


class MonthlyApplicationCount(BaseModel):
    month: str
    count: int = Field(ge=0)


class ApplicationAnalyticsResponse(BaseModel):
    months: int = Field(ge=1, le=60)
    start_month: str
    end_month: str
    total_applications: int = Field(ge=0)
    applications_by_month: list[MonthlyApplicationCount]

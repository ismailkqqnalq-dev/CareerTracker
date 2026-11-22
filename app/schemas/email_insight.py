from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EmailType = Literal["basvuru_alindi", "mulakat_daveti", "degerlendirme", "teklif", "ret", "diger"]


class EmailAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=20_000)
    subject: str = Field(default="", max_length=500)
    sender: str = Field(default="", max_length=320)
    # Başvuru detay ekranından gelindiyse eşleştirme yapılmaz, bu başvuru kullanılır.
    opportunity_id: int | None = Field(default=None, gt=0)
    today: date | None = None

    @field_validator("body")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("body cannot be blank")
        return value


class OpportunitySummary(BaseModel):
    id: int
    company: str | None
    position: str | None
    status: str | None


class SuggestedTask(BaseModel):
    description: str
    due_date: date


class SuggestedUpdate(BaseModel):
    status: str | None
    last_contact_date: date | None
    task: SuggestedTask | None


class EmailAnalysisResponse(BaseModel):
    type: EmailType
    confidence: float
    opportunity: OpportunitySummary | None
    candidates: list[OpportunitySummary]
    suggestion: SuggestedUpdate
    explanation: str


class InboundAddressResponse(BaseModel):
    enabled: bool
    # Sunucuda INBOUND_EMAIL_DOMAIN tanımlı değilse tam adres gösterilemez.
    address: str | None
    domain_configured: bool
    created_at: datetime | None
    verification_code: str | None
    verification_received_at: datetime | None


class InboundEmail(BaseModel):
    """Gelen e-posta servisinden gelen, servisten bağımsız biçim."""

    model_config = ConfigDict(extra="ignore")

    recipient: str = Field(max_length=320)
    sender: str = Field(default="", max_length=320)
    subject: str = Field(default="", max_length=1000)
    text: str = Field(default="", max_length=100_000)


class EmailSuggestionResponse(BaseModel):
    id: int
    opportunity: OpportunitySummary
    email_type: EmailType
    confidence: float
    sender: str
    subject: str
    received_at: datetime
    suggestion: SuggestedUpdate
    state: Literal["pending", "applied", "dismissed"]

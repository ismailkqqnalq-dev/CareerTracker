from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database.session import get_db
from app.models.users import User
from app.schemas.email_insight import EmailAnalysisRequest, EmailAnalysisResponse
from app.services import email_insight_service


router = APIRouter(tags=["email insights"])


@router.post(
    "/email-insights/analyze",
    response_model=EmailAnalysisResponse,
    responses={404: {"description": "Opportunity not found"}},
)
def analyze_email(
    data: EmailAnalysisRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # E-posta metni kişiseldir: saklanmaz ve yanıt ara belleklerde tutulmaz.
    response.headers["Cache-Control"] = "no-store"
    result = email_insight_service.analyze(
        db,
        user_id=current_user.id,
        subject=data.subject,
        body=data.body,
        sender=data.sender,
        opportunity_id=data.opportunity_id,
        today=data.today or date.today(),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return result

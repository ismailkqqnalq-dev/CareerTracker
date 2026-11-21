from datetime import date

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database.session import get_db
from app.models.users import User
from app.schemas.assistant import AssistantQuestion, AssistantReply
from app.services import assistant_service


router = APIRouter(tags=["assistant"])


@router.post("/assistant/ask", response_model=AssistantReply)
def ask_assistant(
    data: AssistantQuestion,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Cevap kullanıcının kişisel kayıtlarını içerir; ara belleklerde tutulmasın.
    response.headers["Cache-Control"] = "no-store"
    return assistant_service.answer(
        db,
        user_id=current_user.id,
        message=data.message,
        today=data.today or date.today(),
    )

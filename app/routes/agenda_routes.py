from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database.session import get_db
from app.models.users import User
from app.schemas.agenda import AgendaResponse
from app.services import agenda_service


router = APIRouter(tags=["agenda"])


@router.get("/agenda", response_model=AgendaResponse)
def get_agenda(
    today: date | None = Query(
        default=None,
        description="Kullanıcının yerel tarihi (YYYY-AA-GG); verilmezse sunucu tarihi kullanılır.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return agenda_service.get_agenda(db, user_id=current_user.id, today=today or date.today())

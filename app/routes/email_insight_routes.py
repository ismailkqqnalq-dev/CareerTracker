from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database.session import get_db
from app.models.users import User
from app.schemas.email_insight import (
    EmailAnalysisRequest,
    EmailAnalysisResponse,
    EmailSuggestionResponse,
    InboundAddressResponse,
    InboundEmail,
)
from app.services import email_insight_service, inbound_email_service as inbound


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


def _address_response(address) -> dict:
    domain = inbound.inbound_domain()
    return {
        "enabled": address is not None,
        "address": f"{address.local_part}@{domain}" if address is not None and domain else None,
        "domain_configured": domain is not None,
        "created_at": address.created_at if address else None,
        "verification_code": address.verification_code if address else None,
        "verification_received_at": address.verification_received_at if address else None,
    }


@router.get("/email-insights/address", response_model=InboundAddressResponse)
def get_inbound_address(response: Response, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    return _address_response(inbound.get_address(db, current_user.id))


@router.post("/email-insights/address", response_model=InboundAddressResponse)
def rotate_inbound_address(response: Response, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Adres oluşturur veya yeniler; eski adrese gelen e-postalar artık işlenmez."""
    response.headers["Cache-Control"] = "no-store"
    return _address_response(inbound.rotate_address(db, current_user.id))


@router.delete("/email-insights/address", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def disable_inbound_address(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    inbound.disable_address(db, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _suggestion_response(suggestion, opportunity) -> dict:
    task = None
    if suggestion.suggested_task_description:
        task = {"description": suggestion.suggested_task_description, "due_date": suggestion.suggested_task_due_date}
    return {
        "id": suggestion.id,
        "opportunity": {
            "id": opportunity.id,
            "company": opportunity.company,
            "position": opportunity.position,
            "status": opportunity.status,
        },
        "email_type": suggestion.email_type,
        "confidence": suggestion.confidence,
        "sender": suggestion.sender,
        "subject": suggestion.subject,
        "received_at": suggestion.received_at,
        "suggestion": {
            "status": suggestion.suggested_status,
            "last_contact_date": suggestion.suggested_last_contact_date,
            "task": task,
        },
        "state": suggestion.state,
    }


@router.get("/email-insights/suggestions", response_model=list[EmailSuggestionResponse])
def list_email_suggestions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return [_suggestion_response(*row) for row in inbound.list_suggestions(db, current_user.id)]


def _resolve(action, db, user_id, suggestion_id):
    try:
        return _suggestion_response(*action(db, user_id, suggestion_id))
    except inbound.SuggestionNotFound:
        raise HTTPException(status_code=404, detail="Suggestion not found") from None
    except inbound.SuggestionNotPending:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "Suggestion is not pending", "error_code": "suggestion_not_pending"},
        )


@router.post(
    "/email-insights/suggestions/{suggestion_id}/apply",
    response_model=EmailSuggestionResponse,
    responses={404: {"description": "Suggestion not found"}, 409: {"description": "Suggestion is not pending"}},
)
def apply_email_suggestion(suggestion_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _resolve(inbound.apply_suggestion, db, current_user.id, suggestion_id)


@router.post(
    "/email-insights/suggestions/{suggestion_id}/dismiss",
    response_model=EmailSuggestionResponse,
    responses={404: {"description": "Suggestion not found"}, 409: {"description": "Suggestion is not pending"}},
)
def dismiss_email_suggestion(suggestion_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _resolve(inbound.dismiss_suggestion, db, current_user.id, suggestion_id)


@router.post(
    "/inbound/email",
    status_code=status.HTTP_202_ACCEPTED,
    responses={401: {"description": "Invalid inbound secret"}, 503: {"description": "Inbound email is not configured"}},
)
def receive_inbound_email(
    data: InboundEmail,
    db: Session = Depends(get_db),
    x_inbound_secret: str | None = Header(default=None),
):
    """Gelen e-posta servisinin çağırdığı uç nokta; kullanıcı oturumu değil, paylaşılan gizli anahtar ister."""
    if inbound.inbound_secret() is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Inbound email is not configured", "error_code": "inbound_disabled"},
        )
    if not inbound.secret_matches(x_inbound_secret):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid inbound secret", "error_code": "inbound_unauthorized"},
        )
    inbound.handle_inbound(
        db,
        recipient=data.recipient,
        sender=data.sender,
        subject=data.subject,
        text=data.text,
        today=date.today(),
    )
    # Adresin var olup olmadığı veya e-postanın işe yarayıp yaramadığı dışarıya söylenmez.
    return {"status": "accepted"}

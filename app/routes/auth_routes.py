from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database.session import get_db
from app.models.users import User
from app.rate_limits import (
    get_client_ip,
    get_rate_limit_settings,
    rate_limit_manager,
    rate_limited_response,
)
from app.schemas.auth import RegisterRequest, TokenResponse, UserResponse
from app.security import create_access_token, registration_is_enabled
from app.services import auth_service


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "Registration is disabled"},
        429: {"description": "Registration rate limit exceeded"},
    },
)
def register(
    request: Request,
    data: RegisterRequest,
    db: Session = Depends(get_db),
):
    settings = get_rate_limit_settings()
    decision = rate_limit_manager.check(
        "register-ip",
        get_client_ip(request),
        settings.register_ip_per_hour,
        "hour",
    )
    if not decision.allowed:
        return rate_limited_response(decision.retry_after)

    if not registration_is_enabled():
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "detail": "Registration is disabled",
                "error_code": "registration_disabled",
            },
        )

    try:
        return auth_service.register_user(db, data.email, data.password)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.post(
    "/token",
    response_model=TokenResponse,
    responses={429: {"description": "Login rate limit exceeded"}},
)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # Swagger'daki "username" alanına e-posta adresini gir.
    settings = get_rate_limit_settings()
    client_ip = get_client_ip(request)
    ip_decision = rate_limit_manager.check(
        "login-ip",
        client_ip,
        settings.login_ip_per_minute,
        "minute",
    )
    if not ip_decision.allowed:
        return rate_limited_response(ip_decision.retry_after)

    # Hash the composite identifier inside the limiter; raw email is not retained.
    pair_identifier = f"{client_ip}:{form_data.username.strip().casefold()}"
    pair_decision = rate_limit_manager.check(
        "login-ip-email",
        pair_identifier,
        settings.login_ip_email_per_minute,
        "minute",
    )
    if not pair_decision.allowed:
        return rate_limited_response(pair_decision.retry_after)

    user = auth_service.authenticate_user(
        db,
        email=form_data.username,
        password=form_data.password,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserResponse)
def read_current_user(
    current_user: User = Depends(get_current_user),
):
    return current_user
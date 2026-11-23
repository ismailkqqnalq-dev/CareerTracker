from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request, Response, status
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
from app.schemas.auth import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.security import (
    CSRF_HEADER_NAME,
    CSRF_HEADER_VALUE,
    REFRESH_COOKIE_NAME,
    create_access_token,
    refresh_cookie_is_secure,
    registration_is_enabled,
)
from app.services import (
    account_export_service,
    auth_service,
    mailer,
    password_reset_service,
    session_service,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, raw_token: str, persistent: bool) -> None:
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        raw_token,
        # Kalıcı değilse çerez tarayıcı kapanınca silinir.
        max_age=int(session_service.PERSISTENT_LIFETIME.total_seconds()) if persistent else None,
        httponly=True,
        secure=refresh_cookie_is_secure(),
        samesite="strict",
        # Proxy /api önekini siler; tarayıcı ile backend farklı yol gördüğü için kök yol.
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        REFRESH_COOKIE_NAME,
        httponly=True,
        secure=refresh_cookie_is_secure(),
        samesite="strict",
        path="/",
    )


def _csrf_rejected(request: Request) -> JSONResponse | None:
    if request.headers.get(CSRF_HEADER_NAME) == CSRF_HEADER_VALUE:
        return None
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": "Missing request header", "error_code": "csrf_header_missing"},
    )


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
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    remember_me: bool = Form(default=False),
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

    _set_refresh_cookie(response, session_service.issue(db, user, remember_me), remember_me)
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={
        401: {"description": "Refresh cookie missing, invalid, expired, rotated or reused"},
        403: {"description": "CSRF header missing"},
        429: {"description": "Refresh rate limit exceeded"},
    },
)
def refresh(request: Request, db: Session = Depends(get_db)):
    rejected = _csrf_rejected(request)
    if rejected:
        return rejected

    settings = get_rate_limit_settings()
    decision = rate_limit_manager.check(
        "refresh-ip",
        get_client_ip(request),
        settings.login_ip_per_minute,
        "minute",
    )
    if not decision.allowed:
        return rate_limited_response(decision.retry_after)

    try:
        issued = session_service.rotate(db, request.cookies.get(REFRESH_COOKIE_NAME))
    except session_service.SessionError as error:
        failure = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Session expired", "error_code": error.error_code},
        )
        # Başka sekmenin yeni çerezi tarayıcıda zaten olabilir; onu silme.
        if error.error_code != "refresh_token_rotated":
            _clear_refresh_cookie(failure)
        return failure

    success = JSONResponse(
        content=TokenResponse(access_token=create_access_token(str(issued.user.id))).model_dump()
    )
    _set_refresh_cookie(success, issued.refresh_token, issued.persistent)
    return success


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={403: {"description": "CSRF header missing"}},
)
def logout(request: Request, db: Session = Depends(get_db)):
    rejected = _csrf_rejected(request)
    if rejected:
        return rejected
    session_service.revoke(db, request.cookies.get(REFRESH_COOKIE_NAME))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_refresh_cookie(response)
    return response


@router.post(
    "/password-reset/request",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        429: {"description": "Password reset rate limit exceeded"},
        503: {"description": "Outgoing email is not configured"},
    },
)
def request_password_reset(
    request: Request,
    data: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Hesap varsa sıfırlama bağlantısı gönderir; yanıt hesabın var olup olmadığını söylemez."""
    if not mailer.email_is_enabled():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": "Password reset is not available",
                "error_code": "password_reset_unavailable",
            },
        )

    settings = get_rate_limit_settings()
    client_ip = get_client_ip(request)
    for scope, identifier, limit in (
        ("password-reset-ip", client_ip, settings.password_reset_ip_per_hour),
        ("password-reset-email", str(data.email).strip().casefold(), settings.password_reset_email_per_hour),
    ):
        decision = rate_limit_manager.check(scope, identifier, limit, "hour")
        if not decision.allowed:
            return rate_limited_response(decision.retry_after)

    created = password_reset_service.create_reset_token(db, str(data.email))
    if created is not None:
        user, raw_token = created
        # SMTP birkaç saniye sürebilir; yanıt beklemeden döner.
        background_tasks.add_task(password_reset_service.send_reset_email, user.email, raw_token)
    return {"detail": "If the account exists, a reset link has been sent."}


@router.post(
    "/password-reset/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={
        400: {"description": "Reset link is invalid, used or expired"},
        429: {"description": "Rate limit exceeded"},
    },
)
def confirm_password_reset(
    request: Request,
    data: PasswordResetConfirm,
    db: Session = Depends(get_db),
):
    settings = get_rate_limit_settings()
    decision = rate_limit_manager.check(
        "password-reset-confirm-ip",
        get_client_ip(request),
        settings.login_ip_per_minute,
        "minute",
    )
    if not decision.allowed:
        return rate_limited_response(decision.retry_after)

    if not password_reset_service.reset_password(db, data.token, data.new_password):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "detail": "Reset link is invalid or expired",
                "error_code": "reset_token_invalid",
            },
        )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    # Bu tarayıcıda eski bir oturum çerezi kaldıysa o da geçersiz; temizlenir.
    _clear_refresh_cookie(response)
    return response


@router.get("/me", response_model=UserResponse)
def read_current_user(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.get("/me/export", response_class=JSONResponse)
def export_current_user_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download every record of the signed-in user as one JSON document."""
    document = account_export_service.build_export(db, current_user)
    filename = f"careertracker-verilerim-{document['exported_at'][:10]}.json"
    return JSONResponse(
        document,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.post(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={403: {"description": "Current password confirmation failed"}},
)
def change_current_user_password(
    request: Request,
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not auth_service.change_password(
        db, current_user, data.current_password, data.new_password
    ):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "detail": "Current password is incorrect",
                "error_code": "password_confirmation_failed",
            },
        )
    # Diğer cihazlardaki oturumlar kapanır; bu tarayıcıya aynı kalıcılıkta yeni oturum verilir.
    persistent = session_service.is_persistent(
        db, current_user.id, request.cookies.get(REFRESH_COOKIE_NAME)
    )
    session_service.revoke_all_for_user(db, current_user.id)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _set_refresh_cookie(response, session_service.issue(db, current_user, persistent), persistent)
    return response


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={403: {"description": "Current password confirmation failed"}},
)
def delete_current_user(
    data: DeleteAccountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not auth_service.delete_user(db, current_user, data.password):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "detail": "Current password is incorrect",
                "error_code": "password_confirmation_failed",
            },
        )
    # Yenileme kayıtları CASCADE ile silindi; tarayıcıdaki çerez de temizlenir.
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_refresh_cookie(response)
    return response

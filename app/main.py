from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.security import validate_security_configuration
from app.services.mailer import validate_mail_configuration
from app.seed_skill_catalog import seed_catalog_on_startup
from app.rate_limits import validate_rate_limit_configuration
from app.record_limits import validate_record_limit_configuration
from app.request_limits import RequestBodySizeLimitMiddleware
from app.response_headers import ResponseSecurityHeadersMiddleware

from app.routes.activity_routes import router as activity_router
from app.routes.contact_routes import router as contact_router
from app.routes.job_analysis_routes import router as job_analysis_router
from app.routes.ocr_routes import router as ocr_router
from app.routes.opportunity_routes import router as opportunity_router
from app.routes.skill_routes import router as skill_router
from app.routes.task_routes import router as task_router
from app.routes.auth_routes import router as auth_router
from app.routes.agenda_routes import router as agenda_router
from app.routes.assistant_routes import router as assistant_router
from app.routes.email_insight_routes import router as email_insight_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    validate_security_configuration()
    validate_rate_limit_configuration()
    validate_record_limit_configuration()
    validate_mail_configuration()
    seed_catalog_on_startup()
    yield


app = FastAPI(title="CareerTracker", lifespan=lifespan)
app.add_middleware(RequestBodySizeLimitMiddleware)
# Outer user middleware also protects request-size rejection responses.
app.add_middleware(ResponseSecurityHeadersMiddleware)


@app.exception_handler(OverflowError)
async def value_out_of_range(_: Request, __: OverflowError) -> JSONResponse:
    # Veritabanı tamsayısına sığmayan bir kimlik ya da takvimin dışına taşan bir tarih
    # (ör. 9999-12-31 + 7 gün) kullanıcı hatasıdır; 500 yerine 422 dön.
    return JSONResponse(
        status_code=422,
        content={"detail": "A number or date is out of the supported range.", "error_code": "value_out_of_range"},
    )


app.include_router(opportunity_router)
app.include_router(activity_router)
app.include_router(task_router)
app.include_router(contact_router)
app.include_router(skill_router)
app.include_router(auth_router)
app.include_router(ocr_router)
app.include_router(job_analysis_router)
app.include_router(agenda_router)
app.include_router(assistant_router)
app.include_router(email_insight_router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "CareerTracker is running."}

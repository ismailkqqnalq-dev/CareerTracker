"""Authenticated, non-persisting job-description text analysis endpoint."""

import json

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth import get_current_user
from app.database.session import get_db
from app.models.users import User
from app.schemas.job_analysis import JobTextAnalysisRequest, JobTextAnalysisResponse
from app.services.job_text_analysis_service import analyze_job_text


router = APIRouter(tags=["job analysis"])
MAX_JOB_TEXT_BYTES = 100_000


def _error(status_code: int, error_code: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail, "error_code": error_code},
        headers={"Cache-Control": "no-store"},
    )


async def _read_body(request: Request) -> bytes:
    raw_length = request.headers.get("content-length")
    if raw_length is not None:
        try:
            content_length = int(raw_length)
        except ValueError:
            raise ValueError("invalid_content_length") from None
        if content_length < 0:
            raise ValueError("invalid_content_length")
        if content_length > MAX_JOB_TEXT_BYTES:
            raise OverflowError

    body = bytearray()
    size = 0
    async for chunk in request.stream():
        remaining = MAX_JOB_TEXT_BYTES + 1 - size
        if remaining > 0:
            body.extend(chunk[:remaining])
        size += len(chunk)
        if size > MAX_JOB_TEXT_BYTES:
            raise OverflowError
    return bytes(body)


@router.post(
    "/job-analysis",
    response_model=JobTextAnalysisResponse,
    responses={
        400: {"description": "Invalid Content-Length"},
        401: {"description": "Authentication required"},
        413: {"description": "Job text exceeds the byte limit"},
        422: {"description": "Job text is empty or invalid"},
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["text"],
                        "properties": {
                            "text": {"type": "string", "maxLength": 100_000}
                        },
                        "additionalProperties": False,
                    }
                }
            },
        }
    },
)
async def analyze_text(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        raw_body = await _read_body(request)
    except OverflowError:
        return _error(413, "job_text_too_large", "Job text exceeds the 100 KB limit.")
    except ValueError:
        return _error(400, "invalid_content_length", "Content-Length must be a non-negative integer.")

    try:
        payload = json.loads(raw_body)
        data = JobTextAnalysisRequest.model_validate(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, TypeError, ValueError):
        return _error(422, "invalid_job_text", "Request must contain a text string.")

    if not data.text.strip():
        return _error(422, "empty_job_text", "Job text cannot be empty.")

    result = await run_in_threadpool(
        analyze_job_text,
        db,
        user_id=current_user.id,
        text=data.text,
    )
    response.headers["Cache-Control"] = "no-store"
    return result

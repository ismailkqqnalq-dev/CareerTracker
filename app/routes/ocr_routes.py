"""Authenticated, non-persisting OCR endpoint for raw image request bodies."""

import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
from threading import BoundedSemaphore

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.auth import get_current_user
from app.models.users import User
from app.schemas.ocr import OcrExtractResponse
from app.services.ocr_engine import OcrEngine, OcrError, get_default_engine
from app.services.ocr_service import MAX_IMAGE_BYTES, OcrResult, extract_text

router = APIRouter(tags=["ocr"])

# One inference at a time per process. RapidOCR's shared-object inference safety
# is not established, and ONNX Runtime can use the CPU cores inside that slot.
OCR_CONCURRENCY_LIMIT = 1
OCR_PER_PROCESS_LIMIT = OCR_CONCURRENCY_LIMIT
OCR_REQUEST_TIMEOUT_SECONDS = 30
_OCR_SLOT = BoundedSemaphore(OCR_CONCURRENCY_LIMIT)
_OCR_EXECUTOR = ThreadPoolExecutor(max_workers=OCR_CONCURRENCY_LIMIT, thread_name_prefix="ocr")

_ERROR_STATUS = {
    "invalid_image_input": 422,
    "empty_image": 422,
    "image_too_large": 413,
    "image_pixel_limit_exceeded": 413,
    "unsupported_image_type": 415,
    "animated_image_unsupported": 415,
    "invalid_image": 422,
    "invalid_ocr_result": 502,
    "ocr_engine_unavailable": 503,
    "ocr_engine_initialization_failed": 503,
    "ocr_engine_failed": 502,
}


def get_ocr_engine() -> OcrEngine:
    """Resolve the lazy default motor without initializing it at app startup."""
    return get_default_engine()


def _content_length(request: Request) -> int | None:
    raw_value = request.headers.get("content-length")
    if raw_value is None:
        return None
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise OcrError("invalid_content_length", "Content-Length must be an integer.") from exc
    if value < 0:
        raise OcrError("invalid_content_length", "Content-Length cannot be negative.")
    if value > MAX_IMAGE_BYTES:
        raise OcrError("image_too_large", "Image exceeds the encoded byte limit.")
    return value


async def _read_image_body(request: Request) -> bytes:
    """Retain at most MAX_IMAGE_BYTES + 1 bytes from ASGI request streaming."""
    _content_length(request)
    body = bytearray()
    size = 0
    async for chunk in request.stream():
        remaining = MAX_IMAGE_BYTES + 1 - size
        if remaining > 0:
            body.extend(chunk[:remaining])
        size += len(chunk)
        if size > MAX_IMAGE_BYTES:
            raise OcrError("image_too_large", "Image exceeds the encoded byte limit.")
    return bytes(body)


def _run_reserved_ocr(data: bytes, engine: OcrEngine) -> OcrResult:
    # The worker owns the slot from submission until actual OCR completion.
    # Request cancellation cannot stop an already-running ONNX inference.
    try:
        return extract_text(data, engine=engine)
    finally:
        _OCR_SLOT.release()


def _submit_reserved_ocr(data: bytes, engine: OcrEngine) -> Future[OcrResult]:
    return _OCR_EXECUTOR.submit(_run_reserved_ocr, data, engine)


async def _await_ocr_worker(future: Future[OcrResult]) -> OcrResult:
    return await asyncio.wait_for(
        asyncio.shield(asyncio.wrap_future(future)),
        timeout=OCR_REQUEST_TIMEOUT_SECONDS,
    )


def _error_response(error: OcrError) -> JSONResponse:
    if error.error_code == "empty_ocr_result":
        return JSONResponse(
            status_code=200,
            content={"text": "", **error.metadata},
            headers={"Cache-Control": "no-store"},
        )
    status_code = _ERROR_STATUS.get(error.error_code)
    if status_code is None:
        status_code = 400 if error.error_code == "invalid_content_length" else 500
    return JSONResponse(
        status_code=status_code,
        content=error.to_payload(),
        headers={"Cache-Control": "no-store"},
    )


@router.post(
    "/ocr/extract",
    response_model=OcrExtractResponse,
    responses={
        400: {"description": "Invalid request headers", "content": {"application/json": {"example": {"detail": "Invalid request", "error_code": "invalid_content_length"}}}},
        401: {"description": "Authentication required"},
        413: {"description": "Encoded image or pixel limit exceeded"},
        415: {"description": "Unsupported or animated image type"},
        422: {"description": "Empty, corrupt, or invalid image"},
        502: {"description": "OCR engine or result failure"},
        503: {"description": "OCR engine unavailable or process slot busy"},
        504: {"description": "OCR exceeded the request wait limit; inference may still be running"},
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "image/png": {"schema": {"type": "string", "format": "binary"}},
                "image/jpeg": {"schema": {"type": "string", "format": "binary"}},
            },
        }
    },
)
async def extract_ocr(
    request: Request,
    current_user: User = Depends(get_current_user),
    engine: OcrEngine = Depends(get_ocr_engine),
):
    # Authentication dependencies resolve before this function reads headers/body.
    del current_user  # Identity is required; results are intentionally not persisted.
    try:
        _content_length(request)
    except OcrError as error:
        return _error_response(error)

    if not _OCR_SLOT.acquire(blocking=False):
        return JSONResponse(
            status_code=503,
            content={"detail": "OCR is busy; try again shortly.", "error_code": "ocr_busy"},
            headers={"Cache-Control": "no-store", "Retry-After": "1"},
        )

    owns_slot = True
    try:
        data = await _read_image_body(request)
        worker = _submit_reserved_ocr(data, engine)
        owns_slot = False  # Worker finally now owns and releases the slot.
        result = await _await_ocr_worker(worker)
        return JSONResponse(
            status_code=200,
            content={
                "text": result.text,
                "width": result.width,
                "height": result.height,
                "image_format": result.image_format,
            },
            headers={"Cache-Control": "no-store"},
        )
    except OcrError as error:
        return _error_response(error)
    except TimeoutError:
        return JSONResponse(
            status_code=504,
            content={"detail": "OCR exceeded the request wait limit.", "error_code": "ocr_timeout"},
            headers={"Cache-Control": "no-store"},
        )
    finally:
        if owns_slot:
            _OCR_SLOT.release()

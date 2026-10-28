import asyncio
from io import BytesIO
import threading

import pytest
from starlette.requests import Request
from PIL import Image

from app.main import app
from app.services.ocr_engine import OcrError
from app.routes import ocr_routes
from app.routes.ocr_routes import get_ocr_engine


def png_bytes():
    stream = BytesIO()
    Image.new("RGB", (24, 12), "white").save(stream, format="PNG")
    return stream.getvalue()


class FakeEngine:
    def __init__(self, text="Python FastAPI"):
        self.text = text
        self.calls = 0

    def recognize(self, image):
        self.calls += 1
        return self.text


def use_engine(client, engine):
    client.app.dependency_overrides[get_ocr_engine] = lambda: engine


def test_ocr_endpoint_requires_auth_before_oversize_rejection(client, monkeypatch):
    monkeypatch.setattr(
        ocr_routes,
        "_content_length",
        lambda request: pytest.fail("unauthenticated requests must not enter body checks"),
    )
    engine = FakeEngine()
    use_engine(client, engine)

    response = client.post("/ocr/extract", content=b"x" * 1025)

    assert response.status_code == 401
    assert engine.calls == 0


def test_authenticated_request_returns_extraction_metadata(authenticated_client):
    engine = FakeEngine()
    use_engine(authenticated_client, engine)

    response = authenticated_client.post(
        "/ocr/extract",
        content=png_bytes(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "text": "Python FastAPI",
        "width": 24,
        "height": 12,
        "image_format": "PNG",
    }
    assert engine.calls == 1
    assert response.headers["cache-control"] == "no-store"


def test_empty_ocr_result_is_success_with_empty_text(authenticated_client):
    use_engine(authenticated_client, FakeEngine(" \n"))

    response = authenticated_client.post("/ocr/extract", content=png_bytes())

    assert response.status_code == 200
    assert response.json() == {
        "text": "",
        "width": 24,
        "height": 12,
        "image_format": "PNG",
    }


def test_empty_request_body_remains_422(authenticated_client):
    use_engine(authenticated_client, FakeEngine())

    response = authenticated_client.post("/ocr/extract", content=b"")

    assert response.status_code == 422
    assert response.json()["error_code"] == "empty_image"


@pytest.mark.parametrize(
    "error_code,status_code",
    [
        ("invalid_image_input", 422),
        ("empty_image", 422),
        ("image_too_large", 413),
        ("image_pixel_limit_exceeded", 413),
        ("unsupported_image_type", 415),
        ("animated_image_unsupported", 415),
        ("invalid_image", 422),
        ("empty_ocr_result", 200),
        ("invalid_ocr_result", 502),
        ("ocr_engine_unavailable", 503),
        ("ocr_engine_initialization_failed", 503),
        ("ocr_engine_failed", 502),
    ],
)
def test_ocr_error_status_mapping(authenticated_client, monkeypatch, error_code, status_code):
    use_engine(authenticated_client, FakeEngine())
    metadata = {"width": 24, "height": 12, "image_format": "PNG"} if error_code == "empty_ocr_result" else None

    def raise_error(*args, **kwargs):
        raise OcrError(error_code, "safe test detail", metadata=metadata)

    monkeypatch.setattr(ocr_routes, "extract_text", raise_error)
    response = authenticated_client.post("/ocr/extract", content=png_bytes())

    assert response.status_code == status_code
    if error_code == "empty_ocr_result":
        assert response.json() == {"text": "", **metadata}
    else:
        assert response.json() == {"detail": "safe test detail", "error_code": error_code}


def make_request(headers=(), chunks=()):
    iterator = iter(chunks)
    calls = []

    async def receive():
        calls.append(True)
        try:
            body = next(iterator)
        except StopIteration:
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.request", "body": body, "more_body": True}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/ocr/extract",
        "raw_path": b"/ocr/extract",
        "query_string": b"",
        "headers": list(headers),
        "server": ("testserver", 80),
        "client": ("testclient", 123),
    }
    return Request(scope, receive), calls


def test_oversize_content_length_is_rejected_before_stream_read(monkeypatch):
    limit = 16
    monkeypatch.setattr(ocr_routes, "MAX_IMAGE_BYTES", limit)
    request, calls = make_request(
        headers=[(b"content-length", str(limit + 1).encode())],
        chunks=[b"x" * (limit + 1)],
    )

    with pytest.raises(OcrError) as error:
        asyncio.run(ocr_routes._read_image_body(request))

    assert error.value.error_code == "image_too_large"
    assert calls == []


@pytest.mark.parametrize("content_length", [None, b"1"])
def test_stream_counter_rejects_chunked_and_lying_length(content_length, monkeypatch):
    limit = 16
    monkeypatch.setattr(ocr_routes, "MAX_IMAGE_BYTES", limit)
    headers = [] if content_length is None else [(b"content-length", content_length)]
    request, calls = make_request(headers=headers, chunks=[b"x" * 10, b"y" * 7, b"z"])

    with pytest.raises(OcrError) as error:
        asyncio.run(ocr_routes._read_image_body(request))

    assert error.value.error_code == "image_too_large"
    assert len(calls) == 2


def test_ocr_busy_is_503(authenticated_client):
    use_engine(authenticated_client, FakeEngine())
    assert ocr_routes._OCR_SLOT.acquire(blocking=False)
    try:
        response = authenticated_client.post("/ocr/extract", content=png_bytes())
    finally:
        ocr_routes._OCR_SLOT.release()

    assert response.status_code == 503
    assert response.json()["error_code"] == "ocr_busy"


def test_request_cancellation_does_not_release_slot_before_worker_finishes():
    started = threading.Event()
    finish = threading.Event()

    class BlockingEngine:
        def recognize(self, image):
            started.set()
            assert finish.wait(timeout=5)
            return "Python"

    assert ocr_routes._OCR_SLOT.acquire(blocking=False)
    future = ocr_routes._submit_reserved_ocr(png_bytes(), BlockingEngine())
    assert started.wait(timeout=5)

    async def cancel_waiter():
        waiter = asyncio.create_task(ocr_routes._await_ocr_worker(future))
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter

    try:
        asyncio.run(cancel_waiter())
        assert not ocr_routes._OCR_SLOT.acquire(blocking=False)
    finally:
        finish.set()
    assert future.result(timeout=5).text == "Python"
    assert ocr_routes._OCR_SLOT.acquire(blocking=False)
    ocr_routes._OCR_SLOT.release()


def test_timeout_does_not_release_slot_before_worker_finishes(monkeypatch):
    started = threading.Event()
    finish = threading.Event()
    monkeypatch.setattr(ocr_routes, "OCR_REQUEST_TIMEOUT_SECONDS", 0.01)

    class BlockingEngine:
        def recognize(self, image):
            started.set()
            assert finish.wait(timeout=5)
            return "Python"

    assert ocr_routes._OCR_SLOT.acquire(blocking=False)
    future = ocr_routes._submit_reserved_ocr(png_bytes(), BlockingEngine())
    assert started.wait(timeout=5)

    with pytest.raises(TimeoutError):
        asyncio.run(ocr_routes._await_ocr_worker(future))
    assert not ocr_routes._OCR_SLOT.acquire(blocking=False)
    finish.set()
    assert future.result(timeout=5).text == "Python"
    assert ocr_routes._OCR_SLOT.acquire(blocking=False)
    ocr_routes._OCR_SLOT.release()


def test_openapi_documents_raw_binary_body_and_responses():
    schema = app.openapi()["paths"]["/ocr/extract"]["post"]
    body = schema["requestBody"]["content"]
    assert body["image/png"]["schema"] == {"type": "string", "format": "binary"}
    assert body["image/jpeg"]["schema"] == {"type": "string", "format": "binary"}
    assert {"401", "413", "415", "422", "502", "503", "504"} <= set(schema["responses"])

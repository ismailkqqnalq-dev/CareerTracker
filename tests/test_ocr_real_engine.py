import importlib.util
from io import BytesIO

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.services.ocr_engine import RapidOCREngine
from app.routes.ocr_routes import get_ocr_engine


@pytest.mark.skipif(
    any(importlib.util.find_spec(name) is None for name in ("rapidocr", "onnxruntime")),
    reason="Optional OCR motor is not installed; install .[ocr] to run the real engine smoke test",
)
def test_real_motor_api_reads_synthetic_english(authenticated_client):
    image = Image.new("RGB", (600, 100), "white")
    ImageDraw.Draw(image).text((20, 20), "Python FastAPI", fill="black", font=ImageFont.load_default(size=32))
    stream = BytesIO()
    image.save(stream, format="PNG")
    authenticated_client.app.dependency_overrides[get_ocr_engine] = lambda: RapidOCREngine()
    response = authenticated_client.post(
        "/ocr/extract",
        content=stream.getvalue(),
        headers={"Content-Type": "image/png"},
    )
    assert response.status_code == 200
    assert "python" in response.json()["text"].lower()

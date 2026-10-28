import importlib.util
from io import BytesIO

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.services.ocr_engine import RapidOCREngine
from app.services.ocr_service import extract_text


@pytest.mark.skipif(
    any(importlib.util.find_spec(name) is None for name in ("rapidocr", "onnxruntime")),
    reason="Optional OCR motor is not installed; install .[ocr] to run the real engine smoke test",
)
def test_real_motor_reads_synthetic_english():
    image = Image.new("RGB", (600, 100), "white")
    ImageDraw.Draw(image).text((20, 20), "Python FastAPI", fill="black", font=ImageFont.load_default(size=32))
    stream = BytesIO()
    image.save(stream, format="PNG")
    result = extract_text(stream.getvalue(), engine=RapidOCREngine())
    assert "python" in result.text.lower()

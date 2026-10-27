from io import BytesIO
from types import SimpleNamespace

import pytest
from app.services import ocr_engine, ocr_service
from app.services.ocr_engine import OcrError, RapidOCREngine
from PIL import Image, PngImagePlugin


def image_bytes(fmt="PNG", size=(16, 16)):
    stream = BytesIO()
    Image.new("RGB", size, "white").save(stream, format=fmt)
    return stream.getvalue()


class FakeEngine:
    def __init__(self, text="İş ilanı: Python"):
        self.text = text
        self.calls = []

    def recognize(self, image):
        self.calls.append((image.mode, image.size))
        return self.text


@pytest.mark.parametrize("fmt", ["PNG", "JPEG"])
def test_reads_content_in_memory(fmt, monkeypatch):
    data = image_bytes(fmt)
    engine = FakeEngine()
    def no_save(*args, **kwargs):
        raise AssertionError("service must not write images")
    monkeypatch.setattr(Image.Image, "save", no_save)
    result = ocr_service.extract_text(data, engine=engine)
    assert result.text == "İş ilanı: Python"
    assert (result.width, result.height, result.image_format) == (16, 16, fmt)
    assert engine.calls == [("RGB", (16, 16))]


@pytest.mark.parametrize("data,code", [
    ("../../some-file.png", "invalid_image_input"),
    (b"", "empty_image"),
    (b"not an image", "invalid_image"),
])
def test_rejects_bad_input_before_engine(data, code):
    engine = FakeEngine()
    with pytest.raises(OcrError) as error:
        ocr_service.extract_text(data, engine=engine)
    assert error.value.error_code == code
    assert error.value.to_payload() == {"detail": error.value.detail, "error_code": code}
    assert engine.calls == []


def test_byte_limit_before_open(monkeypatch):
    monkeypatch.setattr(ocr_service, "MAX_IMAGE_BYTES", 3)
    monkeypatch.setattr(Image, "open", lambda *a, **k: pytest.fail("must check bytes first"))
    with pytest.raises(OcrError, match="byte") as error:
        ocr_service.extract_text(b"1234", engine=FakeEngine())
    assert error.value.error_code == "image_too_large"


def test_pixel_limit_before_decode(monkeypatch):
    data = image_bytes(size=(4, 4))
    monkeypatch.setattr(ocr_service, "MAX_IMAGE_PIXELS", 15)
    monkeypatch.setattr(PngImagePlugin.PngImageFile, "load", lambda *a, **k: pytest.fail("must check header first"))
    with pytest.raises(OcrError) as error:
        ocr_service.extract_text(data, engine=FakeEngine())
    assert error.value.error_code == "image_pixel_limit_exceeded"


def test_pillow_bomb_becomes_explicit_error(monkeypatch):
    data = image_bytes(size=(4, 4))
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 4)
    with pytest.raises(OcrError) as error:
        ocr_service.extract_text(data, engine=FakeEngine())
    assert error.value.error_code == "image_pixel_limit_exceeded"


def test_unsupported_format_uses_content():
    with pytest.raises(OcrError) as error:
        ocr_service.extract_text(image_bytes("BMP"), engine=FakeEngine())
    assert error.value.error_code == "unsupported_image_type"


def test_truncated_image_never_reaches_engine():
    engine = FakeEngine()
    with pytest.raises(OcrError) as error:
        ocr_service.extract_text(image_bytes()[:45], engine=engine)
    assert error.value.error_code == "invalid_image"
    assert engine.calls == []


def test_animated_png_is_rejected():
    stream = BytesIO()
    Image.new("RGB", (8, 8), "white").save(stream, format="PNG", save_all=True,
        append_images=[Image.new("RGB", (8, 8), "black")])
    with pytest.raises(OcrError) as error:
        ocr_service.extract_text(stream.getvalue(), engine=FakeEngine())
    assert error.value.error_code == "animated_image_unsupported"


@pytest.mark.parametrize("text", ["", " \n\t"])
def test_empty_ocr_result_is_explicit(text):
    with pytest.raises(OcrError) as error:
        ocr_service.extract_text(image_bytes(), engine=FakeEngine(text))
    assert error.value.error_code == "empty_ocr_result"


def test_engine_initializes_lazily_and_once(monkeypatch):
    created = []
    def factory(**kwargs):
        created.append(kwargs)
        return lambda image: SimpleNamespace(txts=["Python", "İş ilanı"])
    monkeypatch.setattr(ocr_engine, "_load_rapidocr", lambda: factory)
    engine = RapidOCREngine()
    assert created == []
    for _ in range(2):
        assert ocr_service.extract_text(image_bytes(), engine=engine).text == "Python\nİş ilanı"
    assert len(created) == 1
    assert ocr_engine.get_default_engine() is ocr_engine.get_default_engine()


def test_missing_optional_engine_is_explicit(monkeypatch):
    def missing():
        raise ModuleNotFoundError("rapidocr")
    monkeypatch.setattr(ocr_engine, "_load_rapidocr", missing)
    with pytest.raises(OcrError) as error:
        ocr_service.extract_text(image_bytes(), engine=RapidOCREngine())
    assert error.value.error_code == "ocr_engine_unavailable"


def test_engine_failure_does_not_expose_backend_details():
    class Broken:
        def recognize(self, image):
            raise RuntimeError("private internal path")
    with pytest.raises(OcrError) as error:
        ocr_service.extract_text(image_bytes(), engine=Broken())
    assert error.value.error_code == "ocr_engine_failed"
    assert "private" not in error.value.detail

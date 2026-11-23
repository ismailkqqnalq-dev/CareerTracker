"""Optional CPU OCR adapter. Importing this module does not import an OCR runtime."""

from threading import Lock
from typing import Protocol

from PIL import Image, ImageOps

# Text touching the image edge is often missed by the detector (a tightly
# cropped 1073x120 strip lost 74% of its characters); a white margin fixes it.
# See docs/ocr-baseline.md for the measurements behind these settings.
EDGE_PADDING_PX = 40


class OcrError(Exception):
    """Transport-neutral error compatible with the API's existing error envelope."""

    def __init__(
        self,
        error_code: str,
        detail: str,
        *,
        metadata: dict[str, object] | None = None,
    ):
        super().__init__(detail)
        self.error_code = error_code
        self.detail = detail
        self.metadata = metadata or {}

    def to_payload(self) -> dict[str, str]:
        return {"detail": self.detail, "error_code": self.error_code}


class OcrEngine(Protocol):
    def recognize(self, image: Image.Image) -> str:
        """Read an already validated RGB image without persisting it."""
        ...


def _load_rapidocr():
    # The core application and fake-engine tests must work without either package.
    import onnxruntime  # noqa: F401
    from rapidocr import ModelType, OCRVersion, RapidOCR

    return RapidOCR, ModelType, OCRVersion


class RapidOCREngine:
    """Lazy reusable motor. Only initialization is synchronized, not inference.

    Timeout, cancellation and concurrent inference policies belong to the next slice.
    """

    def __init__(self, lang: str = "tr"):
        # PP-OCRv6 maps "tr" and "ch" to the same multilingual model; this
        # option currently does not select Turkish-specific model weights.
        self.lang = lang
        self._runtime = None
        self._initialization_lock = Lock()

    def _get_runtime(self):
        with self._initialization_lock:
            if self._runtime is None:
                try:
                    factory, model_type, ocr_version = _load_rapidocr()
                except (ImportError, OSError) as exc:
                    raise OcrError("ocr_engine_unavailable", "Install the optional ocr extra to use the OCR motor.") from exc
                try:
                    self._runtime = factory(params={
                        "Det.ocr_version": ocr_version.PPOCRV6,
                        "Det.model_type": model_type.SMALL,
                        "Rec.ocr_version": ocr_version.PPOCRV6,
                        "Rec.model_type": model_type.SMALL,
                        "Rec.lang_type": self.lang,
                        # Postings are upright screenshots; the rotation classifier
                        # only added time and misread lines.
                        "Global.use_cls": False,
                        # The default ("min", 736) upscales the short side, so a wide
                        # strip became a huge input; cap the long side instead.
                        "Det.limit_type": "max",
                        "Det.limit_side_len": 1600,
                    })
                except Exception as exc:
                    raise OcrError("ocr_engine_initialization_failed", "The OCR motor could not be initialized.") from exc
        return self._runtime

    def recognize(self, image: Image.Image) -> str:
        runtime = self._get_runtime()
        try:
            result = runtime(ImageOps.expand(image, border=EDGE_PADDING_PX, fill="white"))
            return "\n".join(result.txts) if result.txts is not None else ""
        except Exception as exc:
            raise OcrError("ocr_engine_failed", "The OCR motor could not process the image.") from exc


_default_engine = RapidOCREngine()


def get_default_engine() -> OcrEngine:
    return _default_engine

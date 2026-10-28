"""Validate bounded image bytes and return raw OCR text; no files or database writes."""

from dataclasses import dataclass
from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

from app.services.ocr_engine import OcrEngine, OcrError, get_default_engine

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
ALLOWED_IMAGE_FORMATS = frozenset({"PNG", "JPEG"})


@dataclass(frozen=True)
class OcrResult:
    text: str
    width: int
    height: int
    image_format: str


def _decode_image(data: bytes) -> tuple[Image.Image, str]:
    if not isinstance(data, bytes):
        raise OcrError("invalid_image_input", "Image input must be bytes, not a path or filename.")
    if not data:
        raise OcrError("empty_image", "Image input is empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise OcrError("image_too_large", "Image exceeds the encoded byte limit.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as header:
                fmt = header.format
                if fmt not in ALLOWED_IMAGE_FORMATS:
                    raise OcrError("unsupported_image_type", "Only PNG and JPEG images are supported.")
                width, height = header.size
                if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                    raise OcrError("image_pixel_limit_exceeded", "Image exceeds the pixel limit.")
                if getattr(header, "n_frames", 1) != 1:
                    raise OcrError("animated_image_unsupported", "Animated images are not supported.")
                header.verify()
            # verify() invalidates the decoder. Reopen only after header limits pass.
            with Image.open(BytesIO(data)) as source:
                source.load()
                oriented = ImageOps.exif_transpose(source)
                try:
                    has_transparency = "A" in oriented.getbands() or "transparency" in oriented.info
                    if has_transparency:
                        rgba = oriented.convert("RGBA")
                        try:
                            image = Image.new("RGB", rgba.size, "white")
                            image.paste(rgba, mask=rgba.getchannel("A"))
                        finally:
                            rgba.close()
                    else:
                        image = oriented.convert("RGB")
                finally:
                    if oriented is not source:
                        oriented.close()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise OcrError("image_pixel_limit_exceeded", "Image exceeds the safe pixel limit.") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise OcrError("invalid_image", "Image is corrupt or cannot be decoded.") from exc
    return image, fmt


def extract_text(data: bytes, *, engine: OcrEngine | None = None) -> OcrResult:
    image, fmt = _decode_image(data)
    try:
        motor = engine if engine is not None else get_default_engine()
        try:
            text = motor.recognize(image)
        except OcrError:
            raise
        except Exception as exc:
            raise OcrError("ocr_engine_failed", "The OCR motor could not process the image.") from exc
        if not isinstance(text, str):
            raise OcrError("invalid_ocr_result", "The OCR motor returned a non-text result.")
        if not text.strip():
            raise OcrError(
                "empty_ocr_result",
                "No readable text was found in the image.",
                metadata={
                    "width": image.width,
                    "height": image.height,
                    "image_format": fmt,
                },
            )
        return OcrResult(text=text, width=image.width, height=image.height, image_format=fmt)
    finally:
        image.close()

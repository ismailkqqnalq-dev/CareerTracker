# OCR baseline and API

This slice provides an in-memory image validation service, an optional OCR adapter,
and an authenticated, non-persisting raw-body API. It adds no UI, tables or migrations.

## Installation

Existing installation commands remain valid:

```sh
python -m pip install -e .
python -m pip install -e ".[dev]"
```

Both install Pillow for validation. Neither requests the `ocr` extra. The main CI
job uses `pip install -e ".[dev]"`; fake-engine service tests always run there.
Real-engine smoke tests skip with an explicit reason when either motor package
is absent. A broken installed motor fails the smoke test rather than skipping.
The separate `ocr-smoke` CI job installs `.[dev,ocr]` on Ubuntu/Python 3.11 and
runs only the real-engine smoke test; it does not add motor dependencies to `test`.

Opt in to the CPU motor:

```sh
python -m pip install -e ".[dev,ocr]"
python -m pytest tests/test_ocr_real_engine.py -q -rs
```

The extra pins RapidOCR 3.10.0 and ONNX Runtime 1.31.0. The publisher's PyPI
records list `rapidocr-3.10.0-py3-none-any.whl` (Python >=3.8,<4) and
`onnxruntime-1.31.0-cp311-cp311-manylinux_2_28_x86_64.whl` (Python >=3.11).
These cover CI's Python 3.11 and x86-64 Ubuntu/glibc >=2.28. A wheel listing is
not a Linux runtime test. Alpine/musl and other architectures require separate validation.

- https://pypi.org/project/rapidocr/3.10.0/#files
- https://pypi.org/project/onnxruntime/1.31.0/#files
- https://rapidai.github.io/RapidOCRDocs/main/en/model_licenses/

RapidOCR's bundled default ONNX model artifacts have their own upstream
PaddleOCR attribution under Apache-2.0; retain the applicable license and notices
when redistributing. CareerTracker does not train these models.

## Service contract

`extract_text(data: bytes, engine=...)` accepts bytes only. No filename or path
argument exists. It limits encoded bytes before opening, then checks format and
header dimensions before verifying/decoding pixels. Accepted formats: PNG/JPEG;
animated PNG is rejected. Limits are named constants: `MAX_IMAGE_BYTES` (10 MiB)
and `MAX_IMAGE_PIXELS` (20 million). Images are never written to disk by the service.

`OcrError` exposes `error_code`, `detail`, and `to_payload()` for the existing
`{"detail": ..., "error_code": ...}` envelope.
Codes: `invalid_image_input`, `empty_image`, `image_too_large`,
`image_pixel_limit_exceeded`, `unsupported_image_type`, `animated_image_unsupported`,
`invalid_image`, `empty_ocr_result`, `invalid_ocr_result`, `ocr_engine_unavailable`,
`ocr_engine_initialization_failed`, `ocr_engine_failed`.

The default adapter is reused process-wide. It imports and creates the real motor
only on first valid request; a small lock guards construction only. The adapter is
not advertised as safe for concurrent inference.

## API slice

`POST /ocr/extract` requires a valid Bearer token (`get_current_user`). It accepts
raw `image/png` or `image/jpeg` bytes, returns `{text, width, height, image_format}`,
and stores neither the image nor the OCR result. The route does not use
`UploadFile`/multipart, so the application does not spool the uploaded body through
Starlette's upload-file temporary-file mechanism. This is not a guarantee about
reverse proxies or the ASGI server, which may buffer request bodies before the
application receives them. The route does not log image bytes, filenames, or OCR text.

The route rejects an announced `Content-Length` over 10 MiB after authentication,
then counts streamed bytes and stops at the 10 MiB + 1 byte boundary even when the
header is absent or lies. Content-Type does not decide whether bytes are trusted;
Pillow validates the actual image content. The route's accumulation buffer is capped
at the configured body limit plus one byte, aside from any larger single chunk already
delivered by the ASGI server. Conversion to immutable bytes briefly copies that buffer.

All service `OcrError` mappings are:

| Error code | HTTP | Meaning |
|---|---:|---|
| `invalid_image_input` | 422 | Non-byte input |
| `empty_image` | 422 | Empty request body |
| `image_too_large` | 413 | Encoded body exceeds 10 MiB |
| `image_pixel_limit_exceeded` | 413 | Header dimensions exceed 20 million pixels |
| `unsupported_image_type` | 415 | Content is not PNG/JPEG |
| `animated_image_unsupported` | 415 | Animated image |
| `invalid_image` | 422 | Corrupt/unreadable image |
| `empty_ocr_result` | 200 | Valid image with no recognized text; empty `text` plus image metadata |
| `invalid_ocr_result` | 502 | Engine returned a non-text value |
| `ocr_engine_unavailable` | 503 | Optional motor package is unavailable |
| `ocr_engine_initialization_failed` | 503 | Motor could not initialize |
| `ocr_engine_failed` | 502 | Inference failed |

The API also returns `invalid_content_length` (400), `ocr_busy` (503), and
`ocr_timeout` (504). One inference slot is allowed per process. A busy process
returns immediately; it does not queue another image. The OCR inference wait limit is 30
seconds (request-body upload time is not included). ONNX inference cannot be cancelled once running, so after a 504 or client
cancellation the worker keeps the slot until its own `finally` releases it. With
multiple Uvicorn workers the limit is per worker, not global.

OpenAPI declares PNG/JPEG raw binary request bodies. In Swagger UI, open
`/docs` → `POST /ocr/extract` → **Try it out**, select a PNG/JPEG file, authorize
with a Bearer token, and **Execute**. The intended request body is the image bytes;
it does not use multipart. The OpenAPI schema is covered by a test, but a live
browser check of Swagger's file selector was not completed in this environment.

## Synthetic evaluation

Provide a local font supporting Turkish (e.g. Arial on Windows or DejaVu Sans on
Linux). No font or user image is downloaded. The CLI requires an explicit font to
avoid silently evaluating replacement glyphs. Use a font whose license permits your use.

```sh
python -m scripts.evaluate_ocr --engine rapidocr --font /path/to/font.ttf
python -m scripts.evaluate_ocr --engine rapidocr --lang ch --font /path/to/font.ttf
```

It prints JSON to stdout; redirect it to a disposable location if needed. It
generates at least 12 deterministic synthetic images in memory. `--engine
module:factory` can supply another trusted local implementation of `OcrEngine`.
Application modules do not import this development script.

The report includes reference/output text, raw CER (NFC/whitespace normalized),
folded CER using the existing `normalize_text`, aligned per-character confusion
counts (including deletions and insertions), and Turkish special-character
accuracy. Folding changes case and I/İ/ı as implemented by `normalize_text`; it
does not remove all diacritics. CER is not semantic accuracy.

The synthetic catalog-terms image contains the canonical names from
`app/skill_catalog.py`, wrapped across several short lines. The report measures
term recall after `normalize_text` and lists the ten most frequent nonmatching
character pairs. This measures exact catalog-name recovery on this synthetic
line layout; it does not measure skill extraction from arbitrary descriptions.

First-call and repeated-call wall/CPU times are reported separately; process CPU
time sums worker threads and may exceed wall time. RSS is approximate and includes
Python/libraries/model memory. OS cache is not flushed. Font hash, dependency
versions and image dimensions accompany results; this synthetic dataset does not
establish accuracy on real screenshots.

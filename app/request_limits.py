"""General request-body limits, excluding endpoints with dedicated limits."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


MAX_GENERAL_REQUEST_BODY_BYTES = 1024 * 1024
DEDICATED_BODY_LIMIT_PATHS = frozenset({"/ocr/extract", "/job-analysis"})


def _error_response(status_code: int, error_code: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail, "error_code": error_code},
        headers={"Cache-Control": "no-store"},
    )


class RequestBodySizeLimitMiddleware:
    """Bound a request body before passing it to application routes."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if (
            scope["type"] != "http"
            or scope.get("path") in DEDICATED_BODY_LIMIT_PATHS
        ):
            await self.app(scope, receive, send)
            return

        content_lengths = [
            value
            for name, value in scope.get("headers", [])
            if name.lower() == b"content-length"
        ]
        if content_lengths:
            if any(value != content_lengths[0] for value in content_lengths[1:]):
                response = _error_response(
                    400, "invalid_content_length", "Content-Length headers conflict."
                )
                await response(scope, receive, send)
                return
            try:
                content_length = int(content_lengths[0])
            except ValueError:
                response = _error_response(
                    400, "invalid_content_length", "Content-Length must be an integer."
                )
                await response(scope, receive, send)
                return
            if content_length < 0:
                response = _error_response(
                    400, "invalid_content_length", "Content-Length cannot be negative."
                )
                await response(scope, receive, send)
                return
            if content_length > MAX_GENERAL_REQUEST_BODY_BYTES:
                response = _error_response(
                    413,
                    "request_too_large",
                    "Request body exceeds the 1 MiB limit.",
                )
                await response(scope, receive, send)
                return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > MAX_GENERAL_REQUEST_BODY_BYTES:
                response = _error_response(
                    413,
                    "request_too_large",
                    "Request body exceeds the 1 MiB limit.",
                )
                await send({
                    "type": "http.response.start",
                    "status": response.status_code,
                    "headers": response.raw_headers,
                })
                await send({
                    "type": "http.response.body",
                    "body": response.body,
                    "more_body": False,
                })
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break

        body_bytes = bytes(body)
        replayed = False

        async def replay_receive() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {
                    "type": "http.request",
                    "body": body_bytes,
                    "more_body": False,
                }
            return await receive()

        await self.app(scope, replay_receive, send)

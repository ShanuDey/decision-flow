"""Request body size cap (security.md section 9): 413 in the shared error shape."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.errors import ErrorResponse


class PayloadTooLarge(HTTPException):
    def __init__(self, max_bytes: int) -> None:
        super().__init__(status_code=413, detail="payload too large")
        self.max_bytes = max_bytes


def _response(max_bytes: int) -> JSONResponse:
    body = ErrorResponse(
        code="payload_too_large",
        message=f"Request body is larger than {max_bytes} bytes",
        details={"max_bytes": max_bytes},
    )
    return JSONResponse(body.model_dump(), status_code=413)


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = dict(scope["headers"]).get(b"content-length", b"")
        if declared.isdigit() and int(declared) > self.max_bytes:
            await _response(self.max_bytes)(scope, receive, send)
            return

        received = 0

        # Chunked bodies have no length up front, so count them as the app reads them.
        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise PayloadTooLarge(self.max_bytes)
            return message

        await self.app(scope, limited_receive, send)


def install_body_limit(app: FastAPI, max_bytes: int) -> None:
    """Call before adding CORS so the 413 still carries CORS headers."""

    async def handle(_: Request, exc: PayloadTooLarge) -> JSONResponse:
        return _response(exc.max_bytes)

    app.add_middleware(BodyLimitMiddleware, max_bytes=max_bytes)
    app.add_exception_handler(PayloadTooLarge, handle)  # type: ignore[arg-type]

"""Every limit number, plus the request body size cap (security.md section 9)."""

from functools import lru_cache

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.errors import ErrorResponse
from app.settings import ROOT_ENV_FILE


class Limits(BaseSettings):
    """0 turns a limit off, except `max_request_bytes`, which always applies."""

    model_config = SettingsConfigDict(env_file=ROOT_ENV_FILE, extra="ignore", frozen=True)

    # Flow drafts are the biggest legitimate payload.
    max_request_bytes: int = Field(1_048_576, ge=1)
    max_concurrent_runs: int = Field(10, ge=0)
    max_concurrent_runs_per_workspace: int = Field(0, ge=0)
    run_timeout_seconds: int = Field(300, ge=0)
    max_nodes: int = Field(50, ge=0)
    max_edges: int = Field(100, ge=0)
    max_flows_per_user: int = Field(20, ge=0)
    limit_notice: str = Field("", max_length=300)
    limit_notice_url: str = Field("", max_length=300)

    @field_validator("limit_notice", "limit_notice_url", mode="after")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("limit_notice_url", mode="after")
    @classmethod
    def _web_link_only(cls, url: str) -> str:
        if url and not url.startswith(("https://", "http://")):
            raise ValueError("limit_notice_url must start with http:// or https://")
        return url

    def notice_details(self) -> dict[str, str]:
        """Extra `details` for a limit error; the link is only offered together with a notice."""
        if not self.limit_notice:
            return {}
        details = {"notice": self.limit_notice}
        if self.limit_notice_url:
            details["notice_url"] = self.limit_notice_url
        return details


@lru_cache
def get_limits() -> Limits:
    return Limits()


class PayloadTooLarge(HTTPException):
    def __init__(self, max_bytes: int) -> None:
        super().__init__(status_code=413, detail="payload too large")
        self.max_bytes = max_bytes


def _response(max_bytes: int, notice: dict[str, str]) -> JSONResponse:
    body = ErrorResponse(
        code="payload_too_large",
        message=f"Request body is larger than {max_bytes} bytes",
        details={"max_bytes": max_bytes, **notice},
    )
    return JSONResponse(body.model_dump(), status_code=413)


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int, notice: dict[str, str] | None = None) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.notice = notice or {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = dict(scope["headers"]).get(b"content-length", b"")
        if declared.isdigit() and int(declared) > self.max_bytes:
            await _response(self.max_bytes, self.notice)(scope, receive, send)
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


def install_body_limit(app: FastAPI, max_bytes: int, notice: dict[str, str] | None = None) -> None:
    """Call before adding CORS so the 413 still carries CORS headers."""

    async def handle(_: Request, exc: PayloadTooLarge) -> JSONResponse:
        return _response(exc.max_bytes, notice or {})

    app.add_middleware(BodyLimitMiddleware, max_bytes=max_bytes, notice=notice)
    app.add_exception_handler(PayloadTooLarge, handle)  # type: ignore[arg-type]

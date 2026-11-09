"""One error shape everywhere: {code, message, details} (api.md section 6)."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.engine.base import FrozenBaseModel


class ErrorResponse(FrozenBaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}


class ApiError(Exception):
    def __init__(
        self, status: int, code: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.body = ErrorResponse(code=code, message=message, details=details or {})


def install_error_handlers(app: FastAPI) -> None:
    async def handle(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(exc.body.model_dump(), status_code=exc.status)

    app.add_exception_handler(ApiError, handle)  # type: ignore[arg-type]

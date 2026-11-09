"""One error shape everywhere: {code, message, details} (api.md section 6)."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
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


def _field(loc: tuple[Any, ...]) -> str:
    # drop the "body"/"path"/"query" prefix
    return ".".join(str(p) for p in loc[1:]) or str(loc[0])


def install_error_handlers(app: FastAPI) -> None:
    async def handle(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(exc.body.model_dump(), status_code=exc.status)

    async def handle_request(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {
                "field": ".".join(str(p) for p in e["loc"][1:]) or str(e["loc"][0]),
                "message": e["msg"],
            }
            for e in exc.errors()
        ]
        first = errors[0]
        body = ErrorResponse(
            code="invalid_request",
            message=f"{first['field']}: {first['message']}",
            details={"field": first["field"], "errors": errors},
        )
        return JSONResponse(body.model_dump(), status_code=422)

    app.add_exception_handler(ApiError, handle)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, handle_request)  # type: ignore[arg-type]

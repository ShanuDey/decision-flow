from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app import tracing
from app.auth import router as auth
from app.auth.deps import current_principal
from app.auth.service import build_authenticator
from app.errors import ErrorResponse, install_error_handlers
from app.flows import router as flows
from app.limits import get_limits, install_body_limit
from app.ops import router as ops
from app.ratelimit import RateLimiters, RateLimitMiddleware, limit_visitor, limit_writes
from app.runs import router as runs
from app.runs.slots import RunSlots
from app.settings import get_settings


def _operation_id(route: APIRoute) -> str:
    # Stable, readable names for the generated web client (health(), ready()).
    return route.name


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Background: an unreachable MLflow must not delay or fail startup.
    tracing.warm_up(get_settings())
    yield
    await tracing.shutdown()
    await app.state.authenticator.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    docs = {} if settings.api_docs_enabled else {"docs_url": None, "redoc_url": None}
    app = FastAPI(
        title="decision-flow api",
        generate_unique_id_function=_operation_id,
        lifespan=_lifespan,
        openapi_url="/openapi.json" if settings.api_docs_enabled else None,
        **docs,
    )

    limits = get_limits()
    app.state.run_slots = RunSlots(limits)
    app.state.rate_limiters = RateLimiters(limits, settings.trusted_proxy)
    # before CORS: stays inside it
    install_body_limit(app, limits.max_request_bytes, limits.notice_details())
    app.add_middleware(RateLimitMiddleware)

    # Strict CORS: only the configured web origin(s), with credentials (security.md section 6).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    install_error_handlers(app)

    # Built here, not in lifespan: a misconfigured app must fail at startup, never serve open.
    app.state.authenticator = build_authenticator(
        settings.auth_providers, settings.auth_allowed_email_domains
    )
    protected: dict[str, Any] = {
        "dependencies": [
            Depends(current_principal),
            Depends(limit_visitor),
            Depends(limit_writes),
        ],
        "responses": {
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
        },
    }
    app.include_router(ops.router)
    app.include_router(auth.router, **protected)
    app.include_router(flows.router, **protected)
    app.include_router(runs.router, **protected)
    return app


app = create_app()

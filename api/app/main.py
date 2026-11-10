from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app import tracing
from app.errors import install_error_handlers
from app.flows import router as flows
from app.limits import install_body_limit
from app.ops import router as ops
from app.runs import router as runs
from app.settings import get_settings


def _operation_id(route: APIRoute) -> str:
    # Stable, readable names for the generated web client (health(), ready()).
    return route.name


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncGenerator[None]:
    # Background: an unreachable MLflow must not delay or fail startup.
    tracing.warm_up(get_settings())
    yield
    await tracing.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="decision-flow api", generate_unique_id_function=_operation_id, lifespan=_lifespan
    )

    install_body_limit(app, settings.max_request_bytes)  # before CORS: stays inside it

    # Strict CORS: only the configured web origin(s), with credentials (security.md section 6).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    install_error_handlers(app)
    app.include_router(ops.router)
    app.include_router(flows.router)
    app.include_router(runs.router)
    return app


app = create_app()

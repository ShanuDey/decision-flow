from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app import tracing
from app.ops import router as ops
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

    # Strict CORS: only the configured web origin(s), with credentials (security.md section 6).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(ops.router)
    return app


app = create_app()

from typing import Annotated

from fastapi import APIRouter, Depends

from app.deployment.schemas import AppConfig
from app.limits import Limits, get_limits
from app.settings import Settings, get_settings

router = APIRouter(tags=["deployment"])


@router.get("/config")
async def config(
    settings: Annotated[Settings, Depends(get_settings)],
    limits: Annotated[Limits, Depends(get_limits)],
) -> AppConfig:
    """Deployment settings the web app needs."""
    return AppConfig(
        delete_mode=settings.delete_mode,
        disabled_node_types=limits.disabled_node_types,
        max_nodes=limits.max_nodes,
        max_edges=limits.max_edges,
        limit_notice=limits.limit_notice,
        limit_notice_url=limits.limit_notice_url,
    )

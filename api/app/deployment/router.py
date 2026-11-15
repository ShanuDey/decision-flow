from typing import Annotated

from fastapi import APIRouter, Depends

from app.deployment.schemas import AppConfig
from app.settings import Settings, get_settings

router = APIRouter(tags=["deployment"])


@router.get("/config")
async def config(settings: Annotated[Settings, Depends(get_settings)]) -> AppConfig:
    """Deployment settings the web app needs."""
    return AppConfig(delete_mode=settings.delete_mode)

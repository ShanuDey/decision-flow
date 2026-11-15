from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.deps import CurrentPrincipal
from app.auth.models import AppConfig, Principal
from app.settings import Settings, get_settings

router = APIRouter(tags=["auth"])


@router.get("/me")
async def me(principal: CurrentPrincipal) -> Principal:
    """The authenticated caller."""
    return principal


@router.get("/config")
async def config(settings: Annotated[Settings, Depends(get_settings)]) -> AppConfig:
    """Deployment settings the web app needs, such as how deleting works."""
    return AppConfig(delete_mode=settings.delete_mode)

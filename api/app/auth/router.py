from fastapi import APIRouter

from app.auth.deps import CurrentPrincipal
from app.auth.models import Principal

router = APIRouter(tags=["auth"])


@router.get("/me")
async def me(principal: CurrentPrincipal) -> Principal:
    """The authenticated caller."""
    return principal

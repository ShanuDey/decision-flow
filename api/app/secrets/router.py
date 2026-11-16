"""HTTP only: parsing, status codes, response shapes. Logic lives in service.py."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.errors import ErrorResponse
from app.limits import Limits, get_limits
from app.secrets import service
from app.secrets.crypto import SecretBox, get_box
from app.secrets.schemas import SecretList, SecretNameParam, SecretPut, SecretSummary
from app.secrets.store import SecretStore, get_secret_store
from app.workspaces.deps import CurrentMember

router = APIRouter(tags=["secrets"])
Store = Annotated[SecretStore, Depends(get_secret_store)]
Box = Annotated[SecretBox, Depends(get_box)]
Lim = Annotated[Limits, Depends(get_limits)]

NOT_FOUND = {404: {"model": ErrorResponse}}


@router.get("/secrets")
async def list_secrets(store: Store, member: CurrentMember) -> SecretList:
    """Lists the workspace's secret names. A value is never returned."""
    rows = await store.list_secrets(member)
    return SecretList(items=[SecretSummary.model_validate(r, from_attributes=True) for r in rows])


@router.put(
    "/secrets/{name}",
    responses={409: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def put_secret(
    name: SecretNameParam,
    body: SecretPut,
    store: Store,
    box: Box,
    member: CurrentMember,
    limits: Lim,
) -> SecretSummary:
    """Creates the secret, or replaces its value. The value is encrypted and cannot be read back.

    Names are uppercase letters, digits and underscores, starting with a letter.
    """
    secret = await service.put_secret(store, box, member, name, body.value, limits)
    return SecretSummary.model_validate(secret, from_attributes=True)


@router.delete("/secrets/{name}", status_code=status.HTTP_204_NO_CONTENT, responses=NOT_FOUND)
async def delete_secret(name: SecretNameParam, store: Store, member: CurrentMember) -> None:
    """Removes the secret for good."""
    await service.delete_secret(store, member, name)

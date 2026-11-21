"""HTTP only: parsing, status codes, response shapes. Logic lives in service.py."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.catalog import service
from app.catalog.remote import CatalogSource, get_catalog_source
from app.catalog.schemas import CatalogListing, InstalledList, InstallRequest, InstallResult
from app.catalog.source import Kind
from app.catalog.store import InstalledStore, get_installed_store
from app.connections.store import ConnectionStore, get_connection_store
from app.errors import ErrorResponse
from app.workspaces.deps import CurrentMember

router = APIRouter(tags=["catalog"])
Store = Annotated[InstalledStore, Depends(get_installed_store)]
Source = Annotated[CatalogSource, Depends(get_catalog_source)]

NOT_FOUND = {404: {"model": ErrorResponse}}
CONFLICT = {409: {"model": ErrorResponse}}
INVALID = {422: {"model": ErrorResponse}}
UNAVAILABLE = {503: {"model": ErrorResponse}}


@router.get("/catalog/index", responses=UNAVAILABLE)
async def get_catalog_index(source: Source) -> CatalogListing:
    """Lists what the Marketplace offers: a summary per item, newest version only.

    Each entry has the `hash` to send when installing it, and the entries it `requires`. The list
    is cached for a few minutes; `stale` is true when the latest refresh failed and this is the
    previous copy. 503 `catalog_unavailable` when the catalog cannot be read and nothing is cached.
    """
    return await service.catalog_listing(source)


@router.post("/catalog/refresh", responses=UNAVAILABLE)
async def refresh_catalog_index(source: Source) -> CatalogListing:
    """Fetches the index again now.

    Within 30 seconds of the last attempt the saved copy is returned instead.
    """
    return await service.catalog_listing(source, force=True)


@router.get("/catalog/installed")
async def list_installed(store: Store, member: CurrentMember) -> InstalledList:
    """Lists the Marketplace items installed in this workspace, with their versions."""
    return await service.list_installed(store, member)


@router.post(
    "/catalog/install",
    status_code=status.HTTP_201_CREATED,
    responses={**NOT_FOUND, **CONFLICT, **INVALID, **UNAVAILABLE},
)
async def install_item(
    body: InstallRequest, store: Store, source: Source, member: CurrentMember
) -> InstallResult:
    """Installs a catalog item in this workspace, or updates it to the given version.

    The server fetches the file itself and checks it against `hash`; 409 `hash_mismatch` means the
    entry changed since you loaded the index. Items it requires are installed first.
    """
    return await service.install(store, source, member, body)


@router.delete(
    "/catalog/installed/{kind}/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**NOT_FOUND, **CONFLICT},
)
async def uninstall_item(
    kind: Kind,
    item_id: str,
    store: Store,
    connections: Annotated[ConnectionStore, Depends(get_connection_store)],
    member: CurrentMember,
) -> None:
    """Removes an installed item. Things already made from it keep their copied settings.

    409 `type_in_use` if connections still use a connection type, and 409 `required_by` if
    another installed item needs it.
    """
    await service.uninstall(store, connections, member, kind, item_id)

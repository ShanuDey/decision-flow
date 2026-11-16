"""Secret use cases. No HTTP types except ApiError."""

from app.errors import ApiError
from app.limits import Limits
from app.secrets.crypto import SecretBox
from app.secrets.models import Secret
from app.secrets.store import SecretStore
from app.workspaces.schemas import Member


async def put_secret(
    store: SecretStore,
    box: SecretBox,
    member: Member,
    name: str,
    value: str,
    limits: Limits,
) -> Secret:
    cap = limits.max_secrets_per_workspace
    if cap and not await store.exists(member, name) and (count := await store.count(member)) >= cap:
        raise ApiError(
            409,
            "secret_limit_reached",
            f"You have {count} secrets; the limit is {cap}.",
            {"limit": cap, "count": count, **limits.notice_details()},
        )
    return await store.put(member, name, box.encrypt(value))


async def delete_secret(store: SecretStore, member: Member, name: str) -> None:
    if not await store.delete(member, name):
        raise ApiError(404, "not_found", "Secret not found")

"""Secret use cases. No HTTP types except ApiError."""

from cryptography.fernet import InvalidToken
from pydantic import SecretStr

from app.engine.run_secrets import RunSecrets
from app.errors import ApiError
from app.limits import Limits
from app.secrets.crypto import BoxFactory, SecretBox
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


async def load_run_secrets(
    store: SecretStore, make_box: BoxFactory, member: Member, names: set[str]
) -> RunSecrets:
    found = await store.get_encrypted(member, names)
    if missing := sorted(names - found.keys()):
        raise ApiError(
            422,
            "secret_not_found",
            f"Secret {', '.join(missing)} not found; add it in Settings > Secrets.",
            {"names": missing},
        )
    box = make_box()
    values: dict[str, SecretStr] = {}
    for name, token in found.items():
        try:
            values[name] = SecretStr(box.decrypt(token))
        except InvalidToken:
            raise ApiError(
                500,
                "secret_unreadable",
                f"Secret {name} cannot be decrypted; ENCRYPTION_KEY may have changed.",
                {"names": [name]},
            ) from None
    return RunSecrets(values=values)


async def delete_secret(store: SecretStore, member: Member, name: str) -> None:
    if not await store.delete(member, name):
        raise ApiError(404, "not_found", "Secret not found")

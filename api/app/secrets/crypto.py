from typing import Annotated

from cryptography.fernet import Fernet, MultiFernet
from fastapi import Depends

from app.errors import ApiError
from app.settings import Settings, get_settings


class SecretBox:
    """The first key encrypts; every key can decrypt, so a key can be rotated in."""

    def __init__(self, keys: list[str]) -> None:
        self._fernet = MultiFernet([Fernet(key) for key in keys])

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, token: str) -> str:
        return self._fernet.decrypt(token.encode()).decode()


def get_box(settings: Annotated[Settings, Depends(get_settings)]) -> SecretBox:
    keys = settings.encryption_keys
    if not keys:
        raise ApiError(
            503,
            "secrets_not_configured",
            "Secrets are off: set ENCRYPTION_KEY on the API server.",
        )
    return SecretBox(keys)

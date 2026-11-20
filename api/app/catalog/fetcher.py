"""Reads raw catalog files from a public https location or a local folder. No parsing here."""

from pathlib import Path
from typing import Protocol

import httpx

TIMEOUT_SECONDS = 5.0


class CatalogUnavailable(Exception):
    """The catalog cannot be read right now (switched off, unreachable, or malformed)."""

    def __init__(self, message: str, *, disabled: bool = False) -> None:
        super().__init__(message)
        self.disabled = disabled


class Fetcher(Protocol):
    async def get(self, relative: str, limit: int, *, missing_ok: bool = False) -> bytes | None:
        """The file's bytes, or None when it is missing and `missing_ok`."""
        ...

    async def aclose(self) -> None: ...


class HttpFetcher:
    """Plain GET with no redirects, a timeout, and a size cap read while streaming."""

    def __init__(self, url: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._url = url
        self._client = httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS, follow_redirects=False, transport=transport
        )

    async def get(self, relative: str, limit: int, *, missing_ok: bool = False) -> bytes | None:
        try:
            async with self._client.stream("GET", f"{self._url}/{relative}") as response:
                if response.status_code == 404 and missing_ok:
                    return None
                if response.status_code != 200:
                    raise CatalogUnavailable(f"The catalog answered {response.status_code}")
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > limit:
                        raise CatalogUnavailable("A catalog file is too large")
                return bytes(data)
        except httpx.HTTPError:
            raise CatalogUnavailable("The catalog could not be reached") from None

    async def aclose(self) -> None:
        await self._client.aclose()


class FolderFetcher:
    def __init__(self, folder: str) -> None:
        self._folder = Path(folder)

    async def get(self, relative: str, limit: int, *, missing_ok: bool = False) -> bytes | None:
        path = self._folder / relative
        try:
            if path.stat().st_size > limit:
                raise CatalogUnavailable("A catalog file is too large")
            return path.read_bytes()
        except FileNotFoundError:
            if missing_ok:
                return None
            raise CatalogUnavailable("The catalog folder has no such file") from None
        except OSError:
            raise CatalogUnavailable("The catalog folder could not be read") from None

    async def aclose(self) -> None:
        return None


def build_fetcher(url: str, transport: httpx.AsyncBaseTransport | None = None) -> Fetcher:
    if not url.lower().startswith(("http://", "https://")):
        return FolderFetcher(url)
    if not url.lower().startswith("https://"):
        raise CatalogUnavailable("CATALOG_URL must use https")
    return HttpFetcher(url, transport)

"""Field types for links that end up in a page the user can click."""

from typing import Annotated

from pydantic import AfterValidator, HttpUrl, TypeAdapter

_HTTP_URL = TypeAdapter(HttpUrl)


def _https_or_empty(value: str) -> str:
    if value and _HTTP_URL.validate_python(value).scheme != "https":
        raise ValueError("must be an https:// link")
    return value


# A link shown as an anchor: empty or https, so `javascript:` and `data:` never get through.
DocsUrl = Annotated[str, AfterValidator(_https_or_empty)]

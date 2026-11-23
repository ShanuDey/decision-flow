from urllib.parse import parse_qsl, urlsplit, urlunsplit


def split_base_url(base: str) -> tuple[str, dict[str, str]]:
    """The base URL without query or fragment, plus the query as parameters.

    An SDK appends its endpoint to the URL text, so a `?` in the base would swallow the endpoint.
    """
    parts = urlsplit(base.strip())
    if parts.username or parts.password:
        raise ValueError("the base URL must not contain a user name or password")
    clean = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))
    return clean, dict(parse_qsl(parts.query, keep_blank_values=True))

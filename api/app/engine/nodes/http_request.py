"""Calls an HTTP API. Every request goes through the SSRF guard in security/ssrf.py."""

import json
import re
import time
from collections.abc import Iterator
from typing import Any, Literal
from urllib.parse import urlencode

import httpx
from pydantic import Field

from app.engine.base import StrictBaseModel
from app.engine.issues import Issue
from app.engine.nodes.base import NodeContext, NodeModel
from app.engine.templates import TemplateError, render
from app.security.ssrf import (
    FRAMING_HEADERS,
    FetchResponse,
    OutboundError,
    OutboundPolicy,
    fetch,
    static_url_problem,
)

HEADER_NAME = re.compile(r"[A-Za-z0-9!#$%&'*+.^_`|~-]+")
RESERVED_HEADERS = FRAMING_HEADERS
# Used when validating without a server policy: only what no server ever allows is flagged.
OPEN_POLICY = OutboundPolicy(allow_private=True, max_bytes=1, timeout_seconds=1)
URL_START = re.compile(r"https?://", re.IGNORECASE)
CONTENT_TYPES = {
    "json": "application/json",
    "form": "application/x-www-form-urlencoded",
    "text": "text/plain; charset=utf-8",
}


class HttpRequestData(StrictBaseModel):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    query: dict[str, str] = Field(default_factory=dict)
    body_type: Literal["none", "json", "form", "text"] = "none"
    # json: any JSON value; form: name -> template; text: one template.
    body: Any = None
    timeout_seconds: int | None = Field(default=None, ge=1)
    fail_on_error_status: bool = False


def _leaves(value: Any, path: str) -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _leaves(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _leaves(item, f"{path}.{index}")


def _as_text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value)


class _Renderer:
    """Fills in templates and stops once the request outgrows the allowed size."""

    def __init__(self, scopes: dict[str, Any], limit: int) -> None:
        self.scopes = scopes
        self.left = limit

    def one(self, template: str, field: str) -> Any:
        try:
            value = render(template, self.scopes)
        except TemplateError as exc:
            raise ValueError(f"{field}: {exc}") from None
        self.left -= len(value) if isinstance(value, str) else len(json.dumps(value))
        if self.left < 0:
            raise ValueError("the request is larger than the allowed size")
        return value

    def tree(self, value: Any, path: str) -> Any:
        if isinstance(value, str):
            return self.one(value, path)
        if isinstance(value, dict):
            return {k: self.tree(v, f"{path}.{k}") for k, v in value.items()}
        if isinstance(value, list):
            return [self.tree(v, f"{path}.{i}") for i, v in enumerate(value)]
        return value


def _response_headers(response: FetchResponse) -> dict[str, str]:
    merged: dict[str, str] = {}
    for name, value in response.headers:
        key = name.lower()
        merged[key] = f"{merged[key]}, {value}" if key in merged else value
    return merged


def _response_body(response: FetchResponse, headers: dict[str, str]) -> Any:
    text = response.body.decode("utf-8", "replace")
    if "json" in headers.get("content-type", "").lower():
        try:
            return json.loads(text)
        except ValueError:
            return text
    return text


class HttpRequestNode(NodeModel):
    type: Literal["http_request"]
    data: HttpRequestData = Field(default_factory=HttpRequestData)

    def templates(self) -> dict[str, str]:
        d = self.data
        found = {"data.url": d.url}
        found.update({f"data.headers.{k}": v for k, v in d.headers.items()})
        found.update({f"data.query.{k}": v for k, v in d.query.items()})
        if d.body_type == "json":
            found.update(_leaves(d.body, "data.body"))
        elif d.body_type == "form" and isinstance(d.body, dict):
            found.update({f"data.body.{k}": v for k, v in d.body.items() if isinstance(v, str)})
        elif d.body_type == "text" and isinstance(d.body, str):
            found["data.body"] = d.body
        return found

    def secret_fields(self) -> set[str]:
        return set(self.templates()) - {"data.url"}

    def check(self, ctx: NodeContext) -> list[Issue]:
        d = self.data
        found: list[tuple[str, str, str]] = []
        if not d.url.strip():
            found.append(("missing_url", "enter the URL to call", "data.url"))
        elif "{{" not in d.url and not URL_START.match(d.url.strip()):
            found.append(("invalid_url", "the URL must start with http:// or https://", "data.url"))
        if (problem := static_url_problem(d.url, ctx.outbound or OPEN_POLICY)) is not None:
            found.append((problem.code, problem.message, "data.url"))
        found += [
            ("invalid_header_name", f"'{name}' is not a valid header name", f"data.headers.{name}")
            for name in d.headers
            if not HEADER_NAME.fullmatch(name)
        ]
        found += [
            (
                "reserved_header",
                f"'{name}' is set by the server and cannot be changed",
                f"data.headers.{name}",
            )
            for name in d.headers
            if name.lower() in RESERVED_HEADERS
        ]
        found += [
            ("invalid_query_name", "a query parameter needs a name", "data.query")
            for name in d.query
            if not name.strip()
        ]
        found += self._body_problems()
        return [Issue(code=c, message=m, node_id=self.id, field=f) for c, m, f in found]

    def _body_problems(self) -> list[tuple[str, str, str]]:
        d = self.data
        if d.body_type == "none":
            problem = "set a body type to send a body"
            return [("invalid_body", problem, "data.body")] if d.body is not None else []
        if d.method == "GET":
            return [("body_not_allowed", "a GET request cannot have a body", "data.body")]
        if d.body_type == "json" and d.body is None:
            return [("invalid_body", "a JSON body is required", "data.body")]
        if d.body_type == "form" and not (
            isinstance(d.body, dict) and all(isinstance(v, str) for v in d.body.values())
        ):
            return [("invalid_body", "a form body is a list of names and text values", "data.body")]
        if d.body_type == "text" and not isinstance(d.body, str):
            return [("invalid_body", "a text body must be text", "data.body")]
        return []

    async def run(self, state: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        d = self.data
        if ctx.outbound is None:
            raise ValueError("outbound requests are not configured")
        scopes = {
            "input": state.get("input", {}),
            "vars": state.get("vars", {}),
            "nodes": state.get("nodes", {}),
            "secrets": ctx.secrets.as_scope(),
        }
        renderer = _Renderer(scopes, ctx.outbound.max_bytes)
        url = _as_text(renderer.one(d.url, "url"))
        query = {k: _as_text(renderer.one(v, f"query.{k}")) for k, v in d.query.items()}
        headers = {k: _as_text(renderer.one(v, f"headers.{k}")) for k, v in d.headers.items()}
        content = self._body(renderer)
        if content is not None and not any(k.lower() == "content-type" for k in headers):
            headers["Content-Type"] = CONTENT_TYPES[d.body_type]
        try:
            target = str(httpx.URL(url).copy_merge_params(query))
        except httpx.InvalidURL:
            raise ValueError("url: the rendered URL is not valid") from None

        policy = ctx.outbound
        if d.timeout_seconds:
            policy = policy.model_copy(
                update={"timeout_seconds": min(d.timeout_seconds, policy.timeout_seconds)}
            )
        started = time.perf_counter()
        try:
            response = await fetch(policy, d.method, target, headers=headers, content=content)
        except OutboundError as exc:
            raise ValueError(f"request failed ({exc.code}): {exc.message}") from None

        received = _response_headers(response)
        ok = 200 <= response.status_code < 300
        if d.fail_on_error_status and not ok:
            raise ValueError(f"the server answered HTTP {response.status_code}")
        output = {
            # Names only: a header, query or body value may hold a secret.
            "request": {
                "method": d.method,
                "url": url,
                "query": list(query),
                "headers": list(headers),
            },
            "status": response.status_code,
            "ok": ok,
            "headers": received,
            "body": _response_body(response, received),
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }
        return {"nodes": {self.id: {"output": output}}}

    def _body(self, renderer: _Renderer) -> bytes | None:
        d = self.data
        if d.body_type == "json":
            return json.dumps(renderer.tree(d.body, "body")).encode()
        if d.body_type == "form":
            fields = {k: _as_text(renderer.one(v, f"body.{k}")) for k, v in d.body.items()}
            return urlencode(fields).encode()
        if d.body_type == "text":
            return _as_text(renderer.one(d.body, "body")).encode()
        return None

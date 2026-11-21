"""`{{ ... }}` fields: plain scope paths resolve directly, anything else is CEL."""

import json
import re
from functools import lru_cache
from typing import Any

from app.engine import expressions
from app.engine.expressions import Compiled
from app.engine.refs import Ref

__all__ = ["Ref", "TemplateError", "references", "render"]

_PATH = re.compile(r"^(input|vars|secrets|nodes|connection)((?:\.[A-Za-z_][A-Za-z0-9_]*)+)$")
_MISSING_KEY = re.compile(r'Key not found in map : ("[^"]*")')


class TemplateError(ValueError):
    pass


def _expr_end(text: str, i: int) -> int:
    """Index of the `}}` closing an expression, skipping string literals and `{...}` maps."""
    depth, quote = 0, ""
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\":
                i += 1
            elif c == quote:
                quote = ""
        elif c in "'\"":
            quote = c
        elif c == "{":
            depth += 1
        elif c == "}":
            if depth == 0 and text.startswith("}}", i):
                return i
            depth = max(depth - 1, 0)
        i += 1
    return -1


def _split(template: str) -> list[str]:
    """Alternates literal text and expression text, starting and ending with literal."""
    parts: list[str] = []
    pos = 0
    while (start := template.find("{{", pos)) >= 0:
        end = _expr_end(template, start + 2)
        if end < 0:
            end = template.find("}}", start + 2)  # unbalanced quote: still report the expression
        if end < 0:
            break
        parts += [template[pos:start], template[start + 2 : end]]
        pos = end + 2
    parts.append(template[pos:])
    return parts


@lru_cache(maxsize=1024)
def _parse(template: str) -> tuple[str | Ref | Compiled, ...]:
    parts: list[str | Ref | Compiled] = []
    for i, chunk in enumerate(_split(template)):
        if i % 2 == 0:
            parts.append(chunk)
            continue
        source = chunk.strip()
        match = _PATH.match(source)
        if match:
            parts.append(Ref(scope=match[1], path=tuple(match[2].lstrip(".").split("."))))
            continue
        try:
            parts.append(expressions.compile(source))
        except expressions.ExpressionError as exc:
            raise TemplateError(f"invalid expression '{source}': {exc}") from exc
    return tuple(parts)


def references(template: str) -> list[Ref]:
    refs: list[Ref] = []
    for part in _parse(template):
        if isinstance(part, Ref):
            refs.append(part)
        elif isinstance(part, Compiled):
            refs.extend(expressions.references(part))
    return refs


def _resolve(ref: Ref, scopes: dict[str, Any]) -> Any:
    value: Any = scopes.get(ref.scope)
    if value is None:
        raise TemplateError(f"{ref} is not available in this field")
    for key in ref.path:
        if not isinstance(value, dict) or key not in value:
            if ref.scope == "secrets":
                raise TemplateError(f"secret {key} is not set; add it in Settings > Secrets")
            if ref.scope == "connection":
                raise TemplateError(
                    f"the connection has no value '{key}'; set it on the connection"
                )
            raise TemplateError(f"{ref} is not set")
        value = value[key]
    return value


def _value(part: Ref | Compiled, scopes: dict[str, Any]) -> Any:
    if isinstance(part, Ref):
        return _resolve(part, scopes)
    try:
        return expressions.evaluate(part, scopes)
    except expressions.ExpressionError as exc:
        reason = _MISSING_KEY.sub(r"\1 is not set", str(exc))
        raise TemplateError(f"expression '{part.source}' failed: {reason}") from exc


def render(template: str, scopes: dict[str, Any]) -> Any:
    """A lone `{{ expr }}` keeps the value's type; mixed text is interpolated into a string."""
    parts = _parse(template)
    if len(parts) == 3 and parts[0] == "" and parts[2] == "":
        return _value(parts[1], scopes)  # type: ignore[arg-type]
    out = []
    for part in parts:
        if isinstance(part, str):
            out.append(part)
        else:
            value = _value(part, scopes)
            out.append(value if isinstance(value, str) else json.dumps(value))
    return "".join(out)

"""Minimal template resolver for Slice 0: `{{ input.a.b }}` and `{{ vars.x }}` references only.

Replaced by the CEL-backed `expressions/` module in slices 1 and 2; callers keep the same API.
"""

import json
import re
from dataclasses import dataclass
from typing import Any

_EXPR = re.compile(r"\{\{(.*?)\}\}")
_PATH = re.compile(r"^(input|vars)((?:\.[A-Za-z_][A-Za-z0-9_]*)+)$")


class TemplateError(ValueError):
    pass


@dataclass(frozen=True)
class Ref:
    scope: str
    path: tuple[str, ...]

    def __str__(self) -> str:
        return ".".join((self.scope, *self.path))


def _parse(template: str) -> list[str | Ref]:
    # re.split with one group alternates literal text and expression text
    parts: list[str | Ref] = []
    for i, chunk in enumerate(_EXPR.split(template)):
        if i % 2 == 0:
            parts.append(chunk)
            continue
        match = _PATH.match(chunk.strip())
        if not match:
            raise TemplateError(
                f"unsupported expression '{chunk.strip()}': "
                "only input.* and vars.* references work yet"
            )
        parts.append(Ref(match[1], tuple(match[2].lstrip(".").split("."))))
    return parts


def references(template: str) -> list[Ref]:
    return [p for p in _parse(template) if isinstance(p, Ref)]


def _resolve(ref: Ref, scopes: dict[str, Any]) -> Any:
    value: Any = scopes[ref.scope]
    for key in ref.path:
        if not isinstance(value, dict) or key not in value:
            raise TemplateError(f"{ref} is not set")
        value = value[key]
    return value


def render(template: str, scopes: dict[str, Any]) -> Any:
    """A lone `{{ ref }}` keeps the value's type; mixed text is interpolated into a string."""
    parts = _parse(template)
    if len(parts) == 3 and parts[0] == "" and parts[2] == "":
        return _resolve(parts[1], scopes)  # type: ignore[arg-type]
    out = []
    for part in parts:
        if isinstance(part, str):
            out.append(part)
        else:
            value = _resolve(part, scopes)
            out.append(value if isinstance(value, str) else json.dumps(value))
    return "".join(out)

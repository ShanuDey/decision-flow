"""CEL expressions: compile, evaluate, references. The only importer of cel_expr_python."""

from functools import lru_cache
from typing import Any

from cel_expr_python import cel

from app.engine.base import FrozenBaseModel
from app.engine.expressions.wire import reference_paths
from app.engine.templates import Ref

SCOPES = ("input", "vars", "nodes")
MAX_LENGTH = 2000

_ENV = cel.NewEnv(variables={s: cel.Type.Map(cel.Type.STRING, cel.Type.DYN) for s in SCOPES})


class ExpressionError(ValueError):
    pass


class Compiled(FrozenBaseModel):
    source: str
    program: Any
    return_type: str


def _message(exc: Exception) -> str:
    text = str(exc).replace("INVALID_ARGUMENT: ", "").replace(" [INVALID_ARGUMENT]", "")
    return text.replace("<input>:", "").removeprefix("ERROR: ").strip()


def compile(source: str) -> Compiled:  # noqa: A001
    return _compile(source)


@lru_cache(maxsize=256)
def _compile(source: str) -> Compiled:
    if len(source) > MAX_LENGTH:
        raise ExpressionError(f"expression is longer than {MAX_LENGTH} characters")
    try:
        program = _ENV.compile(source)
    except RuntimeError as exc:
        raise ExpressionError(_message(exc)) from exc
    return Compiled(source=source, program=program, return_type=program.return_type().name())


def evaluate(compiled: Compiled, scope: dict[str, Any]) -> Any:
    data = {name: scope.get(name, {}) for name in SCOPES}
    try:
        result = compiled.program.eval(data=data)
    except RuntimeError as exc:
        raise ExpressionError(_message(exc)) from exc
    if result.type() == cel.Type.ERROR:  # runtime errors come back as a value, not an exception
        raise ExpressionError(str(result.value()).split(": ", 1)[-1])
    return result.plain_value()


def references(compiled: Compiled) -> list[Ref]:
    paths = reference_paths(compiled.program.serialize())
    return [Ref(scope=p[0], path=tuple(p[1:])) for p in paths if p[0] in SCOPES]

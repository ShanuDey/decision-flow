"""Reads reference paths out of a serialized CEL `CheckedExpr`; the library exposes no AST."""

# field numbers from cel.expr.Expr (cel-spec syntax.proto)
_CONST, _IDENT, _SELECT, _CALL, _LIST, _STRUCT, _COMPREHENSION = 3, 4, 5, 6, 7, 8, 9
_CHECKED_EXPR = 4  # CheckedExpr.expr
_ANY_VALUE = 2  # google.protobuf.Any.value
_STRING_CONST = 6  # Constant.string_value

Message = dict[int, list[bytes | int]]


def _message(buf: bytes) -> Message:
    fields: Message = {}
    i = 0
    while i < len(buf):
        tag, i = _varint(buf, i)
        number, kind = tag >> 3, tag & 7
        value: bytes | int
        if kind == 0:
            value, i = _varint(buf, i)
        elif kind == 2:
            size, i = _varint(buf, i)
            value, i = buf[i : i + size], i + size
        elif kind == 1:
            value, i = int.from_bytes(buf[i : i + 8], "little"), i + 8
        elif kind == 5:
            value, i = int.from_bytes(buf[i : i + 4], "little"), i + 4
        else:
            raise ValueError(f"unsupported wire type {kind}")
        fields.setdefault(number, []).append(value)
    return fields


def _varint(buf: bytes, i: int) -> tuple[int, int]:
    result = shift = 0
    while True:
        byte = buf[i]
        i += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, i
        shift += 7


def _all(msg: Message, number: int) -> list[bytes]:
    return [v for v in msg.get(number, []) if isinstance(v, bytes)]


def _first(msg: Message, number: int) -> bytes | None:
    found = _all(msg, number)
    return found[0] if found else None


def _checked_expr(serialized: bytes) -> bytes:
    # `serialize()` wraps the CheckedExpr in a google.protobuf.Any
    inner = _first(_message(serialized), _ANY_VALUE)
    expr = _first(_message(inner), _CHECKED_EXPR) if inner is not None else None
    if expr is None:
        raise ValueError("unexpected serialized expression layout")
    return expr


def _path(expr: bytes) -> list[str] | None:
    """The dotted path of a pure `a.b['c']` chain, or None if the expression is anything else."""
    msg = _message(expr)
    if (ident := _first(msg, _IDENT)) is not None:
        name = _first(_message(ident), 1)
        return None if name is None else [name.decode()]
    if (select := _first(msg, _SELECT)) is not None:
        parts = _message(select)
        operand, field = _first(parts, 1), _first(parts, 2)
        head = _path(operand) if operand is not None else None
        return None if head is None or field is None else [*head, field.decode()]
    if (call := _first(msg, _CALL)) is not None:
        parts = _message(call)
        args = _all(parts, 3)
        if _first(parts, 2) != b"_[_]" or len(args) != 2:
            return None
        head, key = _path(args[0]), _string_const(args[1])
        return None if head is None or key is None else [*head, key]
    return None


def _string_const(expr: bytes) -> str | None:
    const = _first(_message(expr), _CONST)
    text = _first(_message(const), _STRING_CONST) if const is not None else None
    return None if text is None else text.decode()


def _children(expr: bytes) -> list[bytes]:
    msg = _message(expr)
    out: list[bytes] = []
    if (select := _first(msg, _SELECT)) is not None:
        out += _all(_message(select), 1)
    if (call := _first(msg, _CALL)) is not None:
        parts = _message(call)
        out += _all(parts, 1) + _all(parts, 3)
    if (items := _first(msg, _LIST)) is not None:
        out += _all(_message(items), 1)
    if (struct := _first(msg, _STRUCT)) is not None:
        for entry in _all(_message(struct), 2):
            parts = _message(entry)
            out += _all(parts, 3) + _all(parts, 4)
    if (loop := _first(msg, _COMPREHENSION)) is not None:
        parts = _message(loop)
        for number in (2, 4, 5, 6, 7):  # iter_range, accu_init, loop_condition, loop_step, result
            out += _all(parts, number)
    return out


def reference_paths(serialized: bytes) -> list[list[str]]:
    found: list[list[str]] = []

    def walk(expr: bytes) -> None:
        path = _path(expr)
        if path is not None:
            if path not in found:
                found.append(path)
            return
        for child in _children(expr):
            walk(child)

    walk(_checked_expr(serialized))
    return found

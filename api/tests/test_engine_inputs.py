import json
from pathlib import Path

import pytest

from app.engine.graph import FieldDef, Graph
from app.engine.inputs import InputValidationError, validate_input

FIXTURE = Path(__file__).resolve().parents[2] / "examples" / "flows" / "start-end.json"


def field(type_: str, **kw) -> FieldDef:
    return FieldDef(name="x", type=type_, **kw)


@pytest.mark.parametrize(
    ("type_", "value"),
    [
        ("string", "hi"),
        ("number", 5),
        ("number", 5.5),
        ("boolean", False),
        ("object", {"a": 1}),
        ("array", [1, "a"]),
    ],
)
def test_accepts_matching_types(type_: str, value: object) -> None:
    assert validate_input([field(type_)], {"x": value}) == {"x": value}


@pytest.mark.parametrize(
    ("type_", "value"),
    [
        ("string", 5),
        ("number", "5"),
        ("number", True),
        ("number", float("nan")),
        ("number", float("inf")),
        ("boolean", "true"),
        ("boolean", 1),
        ("object", []),
        ("array", {}),
    ],
)
def test_rejects_mismatched_types_without_coercion(type_: str, value: object) -> None:
    with pytest.raises(InputValidationError) as exc:
        validate_input([field(type_)], {"x": value})
    assert exc.value.issues[0].field == "x"
    assert exc.value.issues[0].message == f"expected {type_}"


def test_enum() -> None:
    f = field("enum", values=["silver", "gold"])
    assert validate_input([f], {"x": "gold"}) == {"x": "gold"}
    with pytest.raises(InputValidationError) as exc:
        validate_input([f], {"x": "bronze"})
    assert "silver" in exc.value.issues[0].message


def test_required_default_and_unknown_fields() -> None:
    fields = [
        FieldDef(name="amount", type="number"),
        FieldDef(name="tier", type="string", required=False, default="silver"),
        FieldDef(name="note", type="string", required=False),
    ]
    assert validate_input(fields, {"amount": 1}) == {"amount": 1, "tier": "silver"}
    assert validate_input(fields, {"amount": 1, "tier": None})["tier"] == "silver"

    with pytest.raises(InputValidationError) as exc:
        validate_input(fields, {"extra": 1})
    assert {(i.field, i.message) for i in exc.value.issues} == {
        ("extra", "unknown input field"),
        ("amount", "required"),
    }


def test_all_bad_fields_are_reported_together() -> None:
    fields = [FieldDef(name="a", type="number"), FieldDef(name="b", type="string")]
    with pytest.raises(InputValidationError) as exc:
        validate_input(fields, {"a": "x", "b": 2})
    assert [i.field for i in exc.value.issues] == ["a", "b"]


def test_golden_fixture_input() -> None:
    graph = Graph.model_validate(json.loads(FIXTURE.read_text()))
    assert validate_input(graph.nodes[0].data.inputs, {"amount": 5000}) == {
        "amount": 5000,
        "tier": "silver",
    }

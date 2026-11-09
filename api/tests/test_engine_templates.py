import pytest

from app.engine.templates import Ref, TemplateError, references, render

SCOPES = {"input": {"amount": 5000, "name": "Ada", "nested": {"k": [1, 2]}}, "vars": {"ok": True}}


def test_lone_reference_keeps_its_type() -> None:
    assert render("{{ input.amount }}", SCOPES) == 5000
    assert render("{{input.amount}}", SCOPES) == 5000
    assert render("{{ vars.ok }}", SCOPES) is True
    assert render("{{ input.nested.k }}", SCOPES) == [1, 2]


def test_mixed_text_interpolates_to_a_string() -> None:
    assert render("Hi {{ input.name }}, total {{ input.amount }}", SCOPES) == "Hi Ada, total 5000"
    assert render("ok={{ vars.ok }}", SCOPES) == "ok=true"


def test_plain_text_passes_through() -> None:
    assert render("no refs", SCOPES) == "no refs"


def test_missing_value_names_the_reference() -> None:
    with pytest.raises(TemplateError, match=r"input\.nope is not set"):
        render("{{ input.nope }}", SCOPES)
    with pytest.raises(TemplateError, match=r"input\.amount\.deeper is not set"):
        render("{{ input.amount.deeper }}", SCOPES)


@pytest.mark.parametrize(
    "expr", ["input.amount > 1", "nodes.a.output", "input", "secrets.X", "1 + 1"]
)
def test_unsupported_expressions_fail_loudly(expr: str) -> None:
    with pytest.raises(TemplateError, match="unsupported expression"):
        render("{{ " + expr + " }}", SCOPES)


def test_references() -> None:
    assert references("a {{ input.x.y }} b {{ vars.z }}") == [
        Ref("input", ("x", "y")),
        Ref("vars", ("z",)),
    ]
    assert references("plain") == []

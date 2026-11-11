import pytest

from app.engine.expressions import ExpressionError, compile, evaluate, references


def refs(source: str) -> list[str]:
    return [str(r) for r in references(compile(source))]


def test_evaluates_with_all_three_scopes() -> None:
    expr = compile("input.income > 50000 && vars.score >= 600 && nodes.start.output.age > 18")
    scope = {
        "input": {"income": 60000},
        "vars": {"score": 700},
        "nodes": {"start": {"output": {"age": 30}}},
    }
    assert evaluate(expr, scope) is True


def test_numbers_compare_across_int_and_float() -> None:
    assert evaluate(compile("input.a > 1.5"), {"input": {"a": 2}}) is True


def test_references_lists_static_paths_once_in_order() -> None:
    source = "input.a > 1 && nodes.start.output.age > 18 && vars['x'] == 1 && input.a < 9"
    assert refs(source) == ["input.a", "nodes.start.output.age", "vars.x"]


def test_references_see_through_macros_and_ternaries_and_ignore_loop_variables() -> None:
    assert refs("input.items.exists(i, i.price > vars.limit)") == [
        "input.items",
        "vars.limit",
    ]
    assert refs("has(input.coupon) ? input.coupon == 'A' : false") == ["input.coupon"]


def test_a_dynamic_index_still_reports_what_it_reads() -> None:
    assert refs("input.m[vars.k] == 1") == ["input.m", "vars.k"]


def test_syntax_errors_point_at_the_position() -> None:
    with pytest.raises(ExpressionError, match=r"1:15: Syntax error"):
        compile("input.income >")


def test_undeclared_names_are_compile_errors() -> None:
    with pytest.raises(ExpressionError, match="undeclared reference to 'secrets.key'"):
        compile("secrets.key == 'x'")


def test_a_missing_key_names_the_key() -> None:
    with pytest.raises(ExpressionError, match='"income"'):
        evaluate(compile("input.income > 1"), {"input": {}})


def test_overlong_expressions_are_rejected() -> None:
    with pytest.raises(ExpressionError, match="longer than"):
        compile("1 + " * 1000 + "1")


def test_return_type_is_reported() -> None:
    assert compile("1 + 1").return_type == "INT"
    assert compile("input.x > 1").return_type == "BOOL"


def test_references_are_never_silently_empty_for_expressions_that_read_scopes() -> None:
    # guards the serialized-expression decoder against a library upgrade changing its layout
    for source in ("input.a > 1", "vars.b", "nodes.n.output.c == 1", "input.xs.exists(x, x > 1)"):
        assert references(compile(source)), source

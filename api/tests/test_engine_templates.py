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


def test_cel_expressions_keep_their_type() -> None:
    assert render("{{ input.amount + 1 }}", SCOPES) == 5001
    assert render("{{ input.amount > 1 }}", SCOPES) is True
    assert render("{{ input.amount > 9999 ? 'big' : 'small' }}", SCOPES) == "small"
    assert render("{{ 1 + 1 }}", SCOPES) == 2


def test_cel_expressions_interpolate_in_mixed_text() -> None:
    assert render("next={{ input.amount + 1 }}", SCOPES) == "next=5001"


def test_cel_references_are_reported() -> None:
    assert references("{{ input.amount + vars.n }}") == [
        Ref(scope="input", path=("amount",)),
        Ref(scope="vars", path=("n",)),
    ]


@pytest.mark.parametrize("expr", ["input.amount +", "nope + 1", "secrets.API_KEY + 'x'"])
def test_invalid_expressions_fail_loudly(expr: str) -> None:
    with pytest.raises(TemplateError, match="invalid expression"):
        render("{{ " + expr + " }}", {**SCOPES, "secrets": {"API_KEY": "s3cret-value"}})


def test_expression_runtime_errors_are_template_errors() -> None:
    with pytest.raises(TemplateError, match="failed"):
        render("{{ input.amount / 0 }}", SCOPES)


def test_secrets_scope_resolves_and_keeps_the_text() -> None:
    scopes = {**SCOPES, "secrets": {"API_KEY": "s3cret-value"}}
    assert render("{{ secrets.API_KEY }}", scopes) == "s3cret-value"
    assert render("Bearer {{ secrets.API_KEY }}", scopes) == "Bearer s3cret-value"
    assert references("{{ secrets.API_KEY }}") == [Ref(scope="secrets", path=("API_KEY",))]


def test_a_missing_secret_says_where_to_add_it() -> None:
    with pytest.raises(TemplateError, match="secret API_KEY is not set; add it in Settings"):
        render("{{ secrets.API_KEY }}", {**SCOPES, "secrets": {}})


def test_a_field_with_no_secrets_scope_cannot_read_one() -> None:
    with pytest.raises(TemplateError, match="is not available in this field"):
        render("{{ secrets.API_KEY }}", SCOPES)


def test_references() -> None:
    assert references("a {{ input.x.y }} b {{ vars.z }}") == [
        Ref(scope="input", path=("x", "y")),
        Ref(scope="vars", path=("z",)),
    ]
    assert references("plain") == []


def test_a_string_or_map_may_contain_braces() -> None:
    assert render("{{ 'a}}b' }}", SCOPES) == "a}}b"
    assert render("{{ {'k': {'n': 1}}['k']['n'] }}", SCOPES) == 1
    assert render('{{ "it\'s" }}', SCOPES) == "it's"


def test_an_unterminated_quote_is_reported_not_ignored() -> None:
    with pytest.raises(TemplateError, match="invalid expression"):
        render("{{ input.name's }}", SCOPES)


def test_a_bare_scope_returns_the_whole_scope() -> None:
    assert render("{{ input }}", SCOPES) == SCOPES["input"]
    assert references("{{ input }}") == [Ref(scope="input", path=())]


def test_a_missing_key_says_which_key() -> None:
    with pytest.raises(TemplateError, match=r'"nope" is not set'):
        render("{{ input.nope + 1 }}", SCOPES)


def test_a_fractional_number_does_not_mix_with_an_int() -> None:
    with pytest.raises(TemplateError, match="failed"):
        render("{{ input.amount + 0.5 }}", SCOPES)
    assert render("{{ double(input.amount) + 0.5 }}", SCOPES) == 5000.5


def test_has_checks_for_a_key() -> None:
    assert render("{{ has(input.name) }}", SCOPES) is True
    assert render("{{ has(input.nope) }}", SCOPES) is False

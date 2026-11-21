import pytest
from pydantic import TypeAdapter, ValidationError

from app.security.links import DocsUrl

link = TypeAdapter(DocsUrl)


@pytest.mark.parametrize("value", ["", "https://docs.github.com/rest"])
def test_an_empty_or_https_link_is_accepted(value: str) -> None:
    assert link.validate_python(value) == value


@pytest.mark.parametrize(
    "value",
    ["javascript:alert(1)", "data:text/html,x", "http://example.com", "//example.com", "docs"],
)
def test_anything_else_is_refused(value: str) -> None:
    with pytest.raises(ValidationError):
        link.validate_python(value)

import json
from pathlib import Path
from typing import Any

import pytest

from app.connections.catalog import BY_ID, DATA, TYPES, load_types
from scripts.export_connection_type_schema import OUTPUT, schema_text


def good(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": 1,
        "id": "acme",
        "name": "Acme",
        "description": "Acme API.",
        "fields": [
            {"name": "api_key", "label": "API key", "secret": True},
            {"name": "hosts", "label": "Allowed hosts"},
        ],
        "auth": {"kind": "bearer", "token": "api_key"},
    }
    return base | changes


def write(directory: Path, name: str, body: dict[str, Any]) -> None:
    (directory / f"{name}.json").write_text(json.dumps(body), encoding="utf-8")


def test_the_shipped_types_load_and_are_ordered_built_in_first() -> None:
    assert [(t.category, t.id) for t in TYPES] == [
        ("builtin", "openai_compatible"),
        ("custom", "api_key_header"),
        ("custom", "basic"),
        ("custom", "bearer"),
    ]
    assert set(BY_ID) == {t.id for t in TYPES}


def test_every_shipped_file_has_the_schema_version_and_a_matching_name() -> None:
    for path in DATA.glob("*.json"):
        body = json.loads(path.read_text(encoding="utf-8"))
        assert body["schema_version"] == 1, path.name
        assert path.stem.replace("-", "_") == body["id"].replace("-", "_"), path.name


def test_a_valid_file_loads(tmp_path: Path) -> None:
    write(tmp_path, "acme", good())
    (kind,) = load_types(tmp_path)
    assert kind.id == "acme" and kind.category == "builtin"


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"schema_version": 2}, "schema_version"),
        ({"id": "Acme Co"}, "id must be lowercase"),
        ({"auth": {"kind": "bearer", "token": "missing"}}, "token 'missing' is not a field"),
        ({"auth": {"kind": "bearer", "token": "hosts"}}, "must be a secret field"),
        ({"auth": {"kind": "script", "code": "print(1)"}}, "kind"),
        ({"script": "print(1)"}, "script"),
        ({"fixed_hosts": ["a.test"], "hosts_from": "hosts"}, "not both"),
        ({"hosts_from": "hosts"}, "must be a url field"),
        ({"fixed_hosts": ["https://a.test"]}, "is not a host name"),
        ({"test_path": "/ping"}, "test_path needs hosts_from"),
        (
            {"fields": [{"name": "api_key", "label": "Key", "secret": True}]},
            "add a 'hosts' field",
        ),
        (
            {
                "fields": [
                    {"name": "api_key", "label": "Key", "secret": True},
                    {"name": "api_key", "label": "Key again"},
                    {"name": "hosts", "label": "Hosts"},
                ]
            },
            "field names must be unique",
        ),
    ],
)
def test_a_file_that_points_at_nothing_or_adds_anything_is_refused(
    tmp_path: Path, changes: dict[str, Any], message: str
) -> None:
    write(tmp_path, "acme", good(**changes))
    with pytest.raises(ValueError, match=message) as raised:
        load_types(tmp_path)
    assert str(raised.value).startswith("acme.json:")


def test_two_files_cannot_share_an_id(tmp_path: Path) -> None:
    write(tmp_path, "one", good())
    write(tmp_path, "two", good(name="Other"))
    with pytest.raises(ValueError, match="already used"):
        load_types(tmp_path)


def test_a_file_that_is_not_json_names_itself(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="broken.json"):
        load_types(tmp_path)


def test_the_committed_schema_matches_the_model() -> None:
    assert OUTPUT.read_text(encoding="utf-8") == schema_text(), (
        "run: uv run python -m scripts.export_connection_type_schema"
    )

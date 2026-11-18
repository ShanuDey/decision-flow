import json
import re
from pathlib import Path
from typing import Any

import pytest

from app.connections.catalog import BY_ID as CONNECTION_TYPES
from app.node_templates.catalog import DATA, TEMPLATES, load_templates
from scripts.export_node_template_schema import OUTPUT, schema_text


def good(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": 1,
        "id": "echo",
        "name": "Echo",
        "description": "Posts a message.",
        "node_type": "http_request",
        "inputs": [{"name": "text", "type": "string"}],
        "data": {
            "method": "POST",
            "url": "https://api.example.com/echo",
            "body_type": "json",
            "body": {"text": "{{ input.text }}"},
        },
    }
    return base | changes


def with_data(**changes: Any) -> dict[str, Any]:
    return good()["data"] | changes


def write(directory: Path, name: str, body: dict[str, Any]) -> None:
    (directory / f"{name}.json").write_text(json.dumps(body), encoding="utf-8")


def test_the_shipped_templates_load_and_use_real_connection_types() -> None:
    assert [t.name for t in TEMPLATES] == sorted(t.name for t in TEMPLATES)
    for template in TEMPLATES:
        assert template.node_type == "http_request"
        if template.connection:
            assert template.connection.type in CONNECTION_TYPES


def test_every_shipped_file_has_the_schema_version_and_a_matching_name() -> None:
    for path in DATA.glob("*.json"):
        body = json.loads(path.read_text(encoding="utf-8"))
        assert body["schema_version"] == 1, path.name
        assert re.fullmatch(r"\d+\.\d+\.\d+", body["version"]), path.name
        assert path.stem.replace("-", "_") == body["id"], path.name


def test_a_valid_file_loads(tmp_path: Path) -> None:
    write(tmp_path, "echo", good())
    (template,) = load_templates(tmp_path)
    assert template.id == "echo" and template.data.method == "POST"


def test_a_secret_header_is_allowed_when_it_is_listed(tmp_path: Path) -> None:
    headers = {"X-Api-Key": "{{ secrets.ECHO_KEY }}"}
    write(tmp_path, "echo", good(secrets=["ECHO_KEY"], data=with_data(headers=headers)))
    assert load_templates(tmp_path)[0].secrets == ["ECHO_KEY"]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"schema_version": 2}, "schema_version"),
        ({"id": "Echo Now"}, "id must be lowercase"),
        ({"script": "x"}, "script"),
        ({"node_type": "subflow"}, "node_type"),
        (
            {"data": with_data(connection_id="3f2b8d6e-1111-4222-8333-444455556666")},
            "connection_id",
        ),
        ({"data": with_data(url="")}, "enter the URL"),
        ({"data": with_data(method="GET")}, "GET request cannot have a body"),
        ({"data": with_data(unknown="x")}, "unknown"),
        ({"data": with_data(body={"text": "{{ input.other }}"})}, "'other' that is not listed"),
        ({"data": with_data(body={"text": "{{ vars.count }}"})}, "only input and secrets"),
        ({"data": with_data(body={"text": "{{ nodes.a.output }}"})}, "only input and secrets"),
        ({"data": with_data(body={"text": "{{ secrets.ECHO_KEY }}"})}, "not listed in secrets"),
        (
            {"data": with_data(url="https://a.com/{{ secrets.K }}"), "secrets": ["K"]},
            "cannot use a secret",
        ),
        ({"secrets": ["ECHO_KEY"]}, "listed but never used"),
        ({"secrets": ["echo key"]}, "capitals"),
        ({"inputs": [{"name": "text"}, {"name": "text"}]}, "input names must be unique"),
        ({"inputs": [{"name": "1bad"}]}, "is not a valid name"),
    ],
)
def test_a_file_that_is_not_a_valid_self_contained_node_is_refused(
    tmp_path: Path, changes: dict[str, Any], message: str
) -> None:
    write(tmp_path, "echo", good(**changes))
    with pytest.raises(ValueError, match=message) as raised:
        load_templates(tmp_path)
    assert str(raised.value).startswith("echo.json:")


@pytest.mark.parametrize(
    ("connection", "message"),
    [
        ({"type": "nope"}, "connection type 'nope' does not exist"),
        ({"type": "bearer", "values": {"unknown": "x"}}, "not a plain field"),
        ({"type": "bearer", "values": {"token": "x"}}, "not a plain field"),
    ],
)
def test_a_connection_that_does_not_exist_or_sets_a_secret_is_refused(
    tmp_path: Path, connection: dict[str, Any], message: str
) -> None:
    write(tmp_path, "echo", good(connection=connection))
    with pytest.raises(ValueError, match=message):
        load_templates(tmp_path)


def test_a_known_connection_with_a_plain_suggestion_is_accepted(tmp_path: Path) -> None:
    connection = {"type": "bearer", "values": {"hosts": "api.example.com"}}
    write(tmp_path, "echo", good(connection=connection))
    assert load_templates(tmp_path)[0].connection is not None


def test_two_files_cannot_share_an_id(tmp_path: Path) -> None:
    write(tmp_path, "one", good())
    write(tmp_path, "two", good(name="Other"))
    with pytest.raises(ValueError, match="already used"):
        load_templates(tmp_path)


def test_a_file_that_is_not_json_names_itself(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="broken.json"):
        load_templates(tmp_path)


def test_the_committed_schema_matches_the_model() -> None:
    assert OUTPUT.read_text(encoding="utf-8") == schema_text(), (
        "run: uv run python -m scripts.export_node_template_schema"
    )

import json
from pathlib import Path
from typing import Any

import pytest

from app.catalog.source import load_files
from scripts.build_catalog_index import MARKETPLACE
from tests.test_catalog_index import put, template_file, type_file

ROOT = MARKETPLACE / "catalog"


def test_the_marketplace_folder_loads_with_every_kind() -> None:
    files = load_files(ROOT)
    assert {f.kind for f in files} == {"connection-type", "node-template", "flow"}
    assert {(f.id, f.version) for f in files} >= {("github", "1.0.0"), ("slack", "1.0.0")}


def test_every_shipped_file_sits_at_its_id_and_version() -> None:
    for path in ROOT.rglob("*.json"):
        body = json.loads(path.read_text(encoding="utf-8"))
        assert path.parent.name == body["id"] and path.stem == body["version"], path


def test_a_template_may_use_a_connection_type_from_the_same_snapshot(tmp_path: Path) -> None:
    put(tmp_path, "connection-types", "acme", "1.0.0", type_file())
    put(tmp_path, "node-templates", "acme_ping", "1.0.0", template_file())
    assert len(load_files(tmp_path)) == 2


@pytest.mark.parametrize(
    ("kind", "body", "where", "message"),
    [
        ("connection-types", type_file(), ("acme", "2.0.0"), "must be <id>/<version>.json"),
        ("connection-types", type_file(), ("other", "1.0.0"), "must be <id>/<version>.json"),
        ("connection-types", type_file(script="x"), ("acme", "1.0.0"), "script"),
        (
            "node-templates",
            template_file(connection={"type": "nope"}),
            ("acme_ping", "1.0.0"),
            "does not exist",
        ),
    ],
)
def test_a_file_in_the_wrong_place_or_shape_is_refused(
    tmp_path: Path, kind: str, body: dict[str, Any], where: tuple[str, str], message: str
) -> None:
    put(tmp_path, kind, *where, body)
    with pytest.raises(ValueError, match=message) as raised:
        load_files(tmp_path)
    assert str(raised.value).startswith(f"{kind}/{where[0]}/{where[1]}.json:")


def test_a_file_that_is_not_json_names_itself(tmp_path: Path) -> None:
    directory = tmp_path / "connection-types" / "acme"
    directory.mkdir(parents=True)
    (directory / "1.0.0.json").write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="connection-types/acme/1.0.0.json"):
        load_files(tmp_path)

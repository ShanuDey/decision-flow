import json
import re

from app.catalog.index import DIRECTORIES, Index, build_index, content_hash
from app.connections.catalog import DATA as CONNECTION_DATA
from app.connections.types import ConnectionType
from app.node_templates.catalog import DATA as TEMPLATE_DATA
from scripts.build_catalog_index import OUTPUT, index_text


def test_the_index_lists_every_shipped_file_once() -> None:
    entries = build_index().entries
    files = len(list(CONNECTION_DATA.glob("*.json"))) + len(list(TEMPLATE_DATA.glob("*.json")))
    assert len(entries) == files
    keys = [(e.kind, e.id) for e in entries]
    assert len(set(keys)) == len(keys)


def test_an_entry_is_a_summary_with_a_versioned_path_and_a_content_hash() -> None:
    for entry in build_index().entries:
        assert entry.path == f"{DIRECTORIES[entry.kind]}/{entry.id}/{entry.version}.json"
        assert re.fullmatch(r"\d+\.\d+\.\d+", entry.version)
        assert re.fullmatch(r"sha256-[0-9a-f]{64}", entry.hash)
        assert set(entry.model_dump()) == {
            "id",
            "kind",
            "name",
            "description",
            "tags",
            "version",
            "hash",
            "path",
        }


def test_the_hash_ignores_formatting_and_key_order_but_not_content() -> None:
    body = {"b": 1, "a": {"y": [1, 2], "x": "é"}}
    assert content_hash(body) == content_hash({"a": {"x": "é", "y": [1, 2]}, "b": 1})
    assert content_hash(body) != content_hash({**body, "b": 2})


def test_changing_a_type_changes_its_hash_but_not_its_path() -> None:
    kind = ConnectionType.model_validate(
        json.loads((CONNECTION_DATA / "bearer.json").read_text(encoding="utf-8"))
    )
    edited = kind.model_copy(update={"description": "Changed."})
    assert content_hash(kind.model_dump(mode="json")) != content_hash(
        edited.model_dump(mode="json")
    )


def test_the_committed_index_matches_the_files() -> None:
    assert OUTPUT.read_text(encoding="utf-8") == index_text(), (
        "run: uv run python -m scripts.build_catalog_index"
    )
    assert Index.model_validate(json.loads(OUTPUT.read_text(encoding="utf-8")))

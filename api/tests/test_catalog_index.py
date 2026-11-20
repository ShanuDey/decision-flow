import json
import re
from pathlib import Path
from typing import Any

from app.catalog.index import CatalogIndex, build_index, content_hash
from app.catalog.source import DIRECTORIES, load_files
from scripts.build_catalog_index import MARKETPLACE, OUTPUT, index_text

SHIPPED = load_files(MARKETPLACE / "catalog")


def put(root: Path, kind: str, item_id: str, version: str, body: dict[str, Any]) -> None:
    directory = root / kind / item_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{version}.json").write_text(json.dumps(body), encoding="utf-8")


def type_file(version: str = "1.0.0", **changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": 1,
        "version": version,
        "id": "acme",
        "name": "Acme",
        "description": "Acme API.",
        "fields": [{"name": "token", "label": "Token", "secret": True}],
        "auth": {"kind": "bearer", "token": "token"},
        "fixed_hosts": ["api.acme.test"],
    }
    return base | changes


def template_file(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": 1,
        "version": "1.0.0",
        "id": "acme_ping",
        "name": "Acme: ping",
        "description": "Pings Acme.",
        "node_type": "http_request",
        "connection": {"type": "acme", "values": {}},
        "data": {"method": "GET", "url": "https://api.acme.test/ping"},
    }
    return base | changes


def test_the_index_lists_the_newest_version_of_each_shipped_item_once() -> None:
    entries = build_index(SHIPPED).entries
    keys = [(e.kind, e.id) for e in entries]
    assert len(set(keys)) == len(keys) == len({(f.kind, f.id) for f in SHIPPED})


def test_an_entry_is_a_summary_with_a_versioned_path_and_a_content_hash() -> None:
    for entry in build_index(SHIPPED).entries:
        assert entry.path == f"{DIRECTORIES[entry.kind]}/{entry.id}/{entry.version}.json"
        assert re.fullmatch(r"\d+\.\d+\.\d+", entry.version)
        assert re.fullmatch(r"sha256-[0-9a-f]{64}", entry.hash)
        assert set(entry.model_dump()) == {
            "id",
            "kind",
            "name",
            "description",
            "icon",
            "tags",
            "version",
            "hash",
            "path",
            "requires",
            "has_readme",
        }


def test_has_readme_is_true_when_a_readme_sits_next_to_the_version_files(tmp_path: Path) -> None:
    put(tmp_path, "connection-types", "acme", "1.0.0", type_file())
    assert [e.has_readme for e in build_index(load_files(tmp_path)).entries] == [False]
    (tmp_path / "connection-types" / "acme" / "README.md").write_text("Hi", encoding="utf-8")
    assert [e.has_readme for e in build_index(load_files(tmp_path)).entries] == [True]
    assert all(e.has_readme for e in build_index(SHIPPED).entries)


def test_a_template_requires_the_connection_type_it_uses_when_that_is_a_marketplace_item() -> None:
    entries = {(e.kind, e.id): e for e in build_index(SHIPPED).entries}
    assert entries[("node-template", "github_create_issue")].requires == ["connection-type/github"]
    assert entries[("connection-type", "github")].requires == []


def test_a_template_on_a_built_in_connection_type_requires_nothing(tmp_path: Path) -> None:
    put(
        tmp_path,
        "node-templates",
        "acme_ping",
        "1.0.0",
        template_file(connection={"type": "bearer", "values": {}}),
    )
    (entry,) = build_index(load_files(tmp_path)).entries
    assert entry.requires == []


def test_the_newest_version_wins_and_an_older_file_stays_readable(tmp_path: Path) -> None:
    put(tmp_path, "connection-types", "acme", "1.2.0", type_file("1.2.0"))
    put(tmp_path, "connection-types", "acme", "1.10.0", type_file("1.10.0"))
    put(tmp_path, "connection-types", "acme", "1.9.0", type_file("1.9.0"))
    files = load_files(tmp_path)
    assert len(files) == 3
    assert [e.version for e in build_index(files).entries] == ["1.10.0"]


def test_the_hash_ignores_formatting_and_key_order_but_not_content() -> None:
    body = {"b": 1, "a": {"y": [1, 2], "x": "é"}}
    assert content_hash(body) == content_hash({"a": {"x": "é", "y": [1, 2]}, "b": 1})
    assert content_hash(body) != content_hash({**body, "b": 2})


def test_changing_a_file_changes_its_hash_but_not_its_path(tmp_path: Path) -> None:
    put(tmp_path, "connection-types", "acme", "1.0.0", type_file())
    before = build_index(load_files(tmp_path)).entries[0]
    put(tmp_path, "connection-types", "acme", "1.0.0", type_file(description="Changed."))
    after = build_index(load_files(tmp_path)).entries[0]
    assert (before.path, before.hash != after.hash) == (after.path, True)


def test_the_committed_index_matches_the_files() -> None:
    assert OUTPUT.read_text(encoding="utf-8") == index_text(), (
        "run: uv run python -m scripts.build_catalog_index"
    )
    assert CatalogIndex.model_validate(json.loads(OUTPUT.read_text(encoding="utf-8")))

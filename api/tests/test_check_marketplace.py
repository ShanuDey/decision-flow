import json
import shutil
from pathlib import Path

import pytest

from scripts.build_catalog_index import MARKETPLACE
from scripts.check_marketplace import check


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    root = tmp_path / "marketplace"
    shutil.copytree(MARKETPLACE, root)
    return root


def test_the_committed_folder_passes() -> None:
    assert check() == []


def test_a_file_at_the_wrong_path_is_reported(folder: Path) -> None:
    source = folder / "catalog" / "connection-types" / "slack" / "1.0.0.json"
    source.rename(source.with_name("1.0.1.json"))
    assert any("must be <id>/<version>.json" in p for p in check(folder))


def test_a_built_in_id_cannot_be_reused(folder: Path) -> None:
    path = folder / "catalog" / "connection-types" / "slack" / "1.0.0.json"
    body = json.loads(path.read_text(encoding="utf-8")) | {"id": "bearer"}
    target = folder / "catalog" / "connection-types" / "bearer"
    target.mkdir()
    (target / "1.0.0.json").write_text(json.dumps(body), encoding="utf-8")
    assert any("built-in id" in p for p in check(folder))


def test_a_stale_index_or_schema_is_reported(folder: Path) -> None:
    (folder / "index.json").write_text("{}", encoding="utf-8")
    (folder / "schemas" / "node-template.schema.json").unlink()
    problems = check(folder)
    assert any(p.startswith("index.json: out of date") for p in problems)
    assert any(p.startswith("schemas/node-template.schema.json: out of date") for p in problems)


def test_a_missing_requirement_is_reported(folder: Path) -> None:
    shutil.rmtree(folder / "catalog" / "connection-types" / "github")
    problems = check(folder)
    assert any("does not exist" in p for p in problems)


def test_an_oversized_file_and_a_stray_file_are_reported(folder: Path) -> None:
    big = folder / "catalog" / "connection-types" / "slack" / "1.0.0.json"
    big.write_text(big.read_text(encoding="utf-8") + " " * (257 * 1024), encoding="utf-8")
    (folder / "catalog" / "connection-types" / "slack" / "notes.txt").write_text("x")
    problems = check(folder)
    assert any("larger than 256 KB" in p for p in problems)
    assert any("notes.txt" in p for p in problems)

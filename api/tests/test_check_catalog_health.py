import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.catalog.health import HealthReport, parse_report
from app.catalog.remote import CatalogSource
from scripts.check_catalog_health import (
    EXIT_BROKEN,
    EXIT_OK,
    EXIT_UNREADABLE,
    build_report,
    main,
)
from tests.conftest import MARKETPLACE

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 11, 21, 3, 0, tzinfo=UTC)
GITHUB_FILE = "catalog/connection-types/github/1.0.0.json"
GITHUB_README = "catalog/connection-types/github/README.md"
GITHUB = "connection-type/github"
ISSUE = "node-template/github_create_issue"


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    target = tmp_path / "marketplace"
    shutil.copytree(MARKETPLACE, target, ignore=shutil.ignore_patterns("__pycache__"))
    return target


async def report_of(folder: Path, previous: HealthReport | None = None) -> HealthReport:
    return await build_report(CatalogSource(str(folder)), previous, NOW)


async def test_a_healthy_catalog_has_every_item_ok(folder: Path) -> None:
    report = await report_of(folder)
    assert {GITHUB, ISSUE} <= set(report.entries)
    assert {(h.status, h.failures, h.reason) for h in report.entries.values()} == {("ok", 0, "")}


async def test_a_file_the_index_lists_but_is_gone_fails(folder: Path) -> None:
    (folder / GITHUB_FILE).unlink()
    report = await report_of(folder)
    assert report.entries[GITHUB].failures == 1
    assert "missing" in report.entries[GITHUB].reason


async def test_a_file_that_no_longer_matches_the_index_fails(folder: Path) -> None:
    path = folder / GITHUB_FILE
    body = json.loads(path.read_text("utf-8"))
    body["description"] = "changed after the index was built"
    path.write_text(json.dumps(body), encoding="utf-8")
    assert "hash" in (await report_of(folder)).entries[GITHUB].reason


async def test_a_file_the_app_cannot_read_any_more_fails(folder: Path) -> None:
    path = folder / GITHUB_FILE
    body = json.loads(path.read_text("utf-8"))
    body["a_field_this_version_does_not_know"] = 1
    path.write_text(json.dumps(body), encoding="utf-8")
    assert "not valid" in (await report_of(folder)).entries[GITHUB].reason


async def test_a_listed_readme_that_is_gone_fails(folder: Path) -> None:
    (folder / GITHUB_README).unlink()
    assert (await report_of(folder)).entries[GITHUB].failures == 1


async def test_an_item_needing_a_failing_item_fails_too(folder: Path) -> None:
    (folder / GITHUB_FILE).unlink()
    report = await report_of(folder)
    assert report.entries[ISSUE].failures == 1
    assert GITHUB in report.entries[ISSUE].reason


async def test_two_failures_in_a_row_break_an_item_and_a_pass_clears_it(folder: Path) -> None:
    path = folder / GITHUB_FILE
    saved = path.read_bytes()
    path.unlink()
    first = await report_of(folder)
    assert (first.entries[GITHUB].status, first.entries[GITHUB].failures) == ("ok", 1)
    second = await report_of(folder, first)
    assert (second.entries[GITHUB].status, second.entries[GITHUB].failures) == ("broken", 2)
    path.write_bytes(saved)
    third = await report_of(folder, second)
    assert (third.entries[GITHUB].status, third.entries[GITHUB].failures) == ("ok", 0)


async def test_an_item_that_left_the_catalog_leaves_the_report(folder: Path) -> None:
    previous = await report_of(folder)
    index = json.loads((folder / "index.json").read_text("utf-8"))
    index["entries"] = [e for e in index["entries"] if e["id"] != "slack"]
    (folder / "index.json").write_text(json.dumps(index), encoding="utf-8")
    assert "connection-type/slack" not in (await report_of(folder, previous)).entries


class TestMain:
    def run(self, folder: Path, out: Path, *extra: str) -> int:
        return main(["--catalog-url", str(folder), "--out", str(out), *extra])

    def test_writes_the_report_and_exits_zero_when_all_pass(
        self, folder: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        out = tmp_path / "health.json"
        assert self.run(folder, out) == EXIT_OK
        assert parse_report(out.read_bytes()) is not None
        assert "0 broken" in capsys.readouterr().out

    def test_exits_three_but_still_writes_when_something_is_broken(
        self, folder: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (folder / GITHUB_FILE).unlink()
        out, previous = tmp_path / "health.json", tmp_path / "previous.json"
        assert self.run(folder, previous) == EXIT_OK
        assert self.run(folder, out, "--previous", str(previous)) == EXIT_BROKEN
        assert f"broken: {GITHUB}" in capsys.readouterr().err
        written = parse_report(out.read_bytes())
        assert written is not None and written.entries[GITHUB].status == "broken"

    def test_an_unreadable_catalog_writes_nothing(self, tmp_path: Path) -> None:
        out = tmp_path / "health.json"
        assert self.run(tmp_path / "nowhere", out) == EXIT_UNREADABLE
        assert not out.exists()

    def test_a_missing_or_bad_previous_report_starts_counting_afresh(
        self, folder: Path, tmp_path: Path
    ) -> None:
        bad = tmp_path / "previous.json"
        bad.write_text("{", encoding="utf-8")
        out = tmp_path / "health.json"
        assert self.run(folder, out, "--previous", str(bad)) == EXIT_OK
        assert self.run(folder, out, "--previous", str(tmp_path / "absent.json")) == EXIT_OK

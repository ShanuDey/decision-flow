"""Exit 0: all pass; 3: some broken (report still written); 1: catalog unreadable (no write)."""

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from app.catalog.fetcher import CatalogUnavailable
from app.catalog.health import HealthReport, next_health, parse_report
from app.catalog.index import IndexEntry, file_hash
from app.catalog.remote import CatalogItemInvalid, CatalogItemMissing, CatalogSource
from app.settings import DEFAULT_CATALOG_URL

CONCURRENCY = 8
EXIT_OK, EXIT_UNREADABLE, EXIT_BROKEN = 0, 1, 3


def key_of(entry: IndexEntry) -> str:
    return f"{entry.kind}/{entry.id}"


async def failure_of(source: CatalogSource, entry: IndexEntry) -> str | None:
    try:
        file = await source.read(entry.kind, entry.id, entry.version)
        if file_hash(file) != entry.hash:
            return "the file does not match the hash in index.json"
        if entry.has_readme:
            await source.readme(entry.kind, entry.id)
    except CatalogItemMissing:
        return "a file the index lists is missing"
    except CatalogItemInvalid as exc:
        return f"not valid for this version of the app: {exc}"
    except CatalogUnavailable as exc:
        return str(exc)
    return None


async def build_report(
    source: CatalogSource, previous: HealthReport | None, now: datetime
) -> HealthReport:
    entries = (await source.index()).index.entries
    gate = asyncio.Semaphore(CONCURRENCY)

    async def check(entry: IndexEntry) -> str | None:
        async with gate:
            return await failure_of(source, entry)

    outcomes = await asyncio.gather(*(check(e) for e in entries))
    results = {key_of(e): why for e, why in zip(entries, outcomes, strict=True)}
    for entry in entries:
        broken_need = next((n for n in entry.requires if results.get(n)), None)
        if results[key_of(entry)] is None and broken_need:
            results[key_of(entry)] = f"it needs {broken_need}, which is failing"

    before = previous.entries if previous else {}
    return HealthReport(
        generated_at=now,
        entries={key: next_health(before.get(key), why, now) for key, why in results.items()},
    )


def render(report: HealthReport) -> str:
    return json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def broken_lines(report: HealthReport) -> list[str]:
    return [
        f"broken: {key}: {item.reason}"
        for key, item in sorted(report.entries.items())
        if item.status == "broken"
    ]


def read_previous(path: Path | None) -> HealthReport | None:
    if path is None or not path.is_file():
        return None
    return parse_report(path.read_bytes())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--catalog-url", default=DEFAULT_CATALOG_URL)
    parser.add_argument("--previous", type=Path, help="the last health.json, to count failures")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    async def run() -> HealthReport:
        source = CatalogSource(args.catalog_url)
        try:
            return await build_report(source, read_previous(args.previous), datetime.now(UTC))
        finally:
            await source.aclose()

    try:
        report = asyncio.run(run())
    except CatalogUnavailable as exc:
        print(f"could not read the catalog: {exc}", file=sys.stderr)
        return EXIT_UNREADABLE

    args.out.write_text(render(report), encoding="utf-8", newline="\n")
    problems = broken_lines(report)
    failing = [k for k, v in report.entries.items() if v.failures]
    print(f"checked {len(report.entries)} items, {len(failing)} failing, {len(problems)} broken")
    for line in problems:
        print(line, file=sys.stderr)
    return EXIT_BROKEN if problems else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

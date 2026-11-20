"""Check the marketplace/ folder the way the app reads it; exits 1 and lists every problem."""

import sys
from pathlib import Path

from app.catalog.index import build_index
from app.catalog.remote import ID, MAX_FILE_BYTES, MAX_INDEX_BYTES, VERSION
from app.catalog.source import DIRECTORIES, load_files
from scripts.build_catalog_index import MARKETPLACE, index_text
from scripts.export_connection_type_schema import schema_text as connection_schema_text
from scripts.export_node_template_schema import schema_text as template_schema_text

MAX_README_BYTES = 64 * 1024


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def check(root: Path = MARKETPLACE) -> list[str]:
    problems: list[str] = []
    catalog = root / "catalog"

    for path in sorted(p for p in catalog.rglob("*") if p.is_file()):
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        if path.name == "README.md":
            if size > MAX_README_BYTES:
                problems.append(f"{relative}: larger than {MAX_README_BYTES // 1024} KB")
        elif path.suffix == ".json":
            if size > MAX_FILE_BYTES:
                problems.append(f"{relative}: larger than {MAX_FILE_BYTES // 1024} KB")
            if not VERSION.fullmatch(path.stem):
                problems.append(f"{relative}: the file name must be a version such as 1.0.0")
        else:
            problems.append(f"{relative}: only <version>.json and README.md belong here")
        if not ID.fullmatch(path.parent.name):
            problems.append(f"{relative}: the folder name must be an id like github_create_issue")
        if path.parent.parent.name not in DIRECTORIES.values():
            problems.append(f"{relative}: must be in {' or '.join(sorted(DIRECTORIES.values()))}")

    try:
        files = load_files(catalog)
    except ValueError as exc:
        return [*problems, str(exc)]

    seen: set[tuple[str, str, str]] = set()
    for file in files:
        key = (file.kind, file.id, file.version)
        if key in seen:
            problems.append(f"{file.path}: duplicate {file.kind} {file.id} {file.version}")
        seen.add(key)

    entries = build_index(files).entries
    listed = {f"{e.kind}/{e.id}" for e in entries}
    for entry in entries:
        for need in entry.requires:
            if need not in listed:
                problems.append(f"{entry.path}: requires {need}, which is not in the catalog")

    expected = {
        root / "index.json": index_text(root),
        root / "schemas" / "connection-type.schema.json": connection_schema_text(),
        root / "schemas" / "node-template.schema.json": template_schema_text(),
    }
    for path, text in expected.items():
        if not path.is_file() or _text(path) != text:
            name = path.relative_to(root).as_posix()
            problems.append(f"{name}: out of date; run the matching script in api/scripts")
    index = root / "index.json"
    if index.is_file() and index.stat().st_size > MAX_INDEX_BYTES:
        problems.append("index.json: larger than the API will read")
    return problems


def main() -> int:
    problems = check()
    for problem in problems:
        print(problem, file=sys.stderr)
    if not problems:
        print("marketplace: ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

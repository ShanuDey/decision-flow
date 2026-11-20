# Marketplace

The items every installation can install from its Marketplace page. The API fetches `index.json` and one file per install from this folder on GitHub (see `CATALOG_URL` in the configuration docs). Nothing here is bundled into the app.

```
index.json                                        generated list of the newest version of each item
schemas/                                          generated JSON Schemas for the two file kinds
catalog/connection-types/<id>/<version>.json      a connection type
catalog/node-templates/<id>/<version>.json        a request template
catalog/<kind>/<id>/README.md                     optional notes shown on the docs page of the item
```

Built-in items live in `api/app/connections/data` and `api/app/node_templates/data` and are not listed here.

## Add or change an item

1. Add `catalog/<kind>/<id>/<version>.json`. The id is lower case letters, digits and `_`, starting with a letter; the version is `major.minor.patch`; the path must match the `id` and `version` inside the file. Check your file against `schemas/`.
2. A published version never changes: to change an item, add a new version file. Older versions stay readable.
3. Do not reuse the id of a built-in item. A template's connection type must be built in or in this catalog.
4. Optionally add a `README.md` next to the version files: setup steps and anything a user should know. Keep the JSON `description` to one line.
5. From the repo root, regenerate the derived files and check everything:

```
uv --directory api run python -m scripts.build_catalog_index
uv --directory api run python -m scripts.export_connection_type_schema
uv --directory api run python -m scripts.export_node_template_schema
make check-marketplace
```

Pull requests that touch this folder run `check-marketplace` in CI. It loads every file with the app's own loaders, checks paths, ids and requirements, caps file sizes, and fails when `index.json` or `schemas/` are out of date. Files must stay under 256 KB.

Merging to `main` publishes the change: apps pick it up when their cached index expires (5 minutes), and the docs catalog pages are rebuilt.

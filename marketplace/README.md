# Marketplace

The items every installation can install from its Marketplace page. The API fetches `index.json` and one file per install from this folder on GitHub (see `CATALOG_URL` in the configuration docs). Nothing here is bundled into the app.

```
index.json                                        generated list of the newest version of each item
schemas/                                          generated JSON Schemas for the three file kinds
catalog/connection-types/<id>/<version>.json      a connection type
catalog/node-templates/<id>/<version>.json        a request template
catalog/flows/<id>/<version>.json                 a flow: a graph plus the connections it needs
catalog/<kind>/<id>/README.md                     optional notes shown on the docs page of the item
```

Built-in items live in `api/app/connections/data` and `api/app/node_templates/data` and are not listed here.

## Add or change an item

1. Add `catalog/<kind>/<id>/<version>.json`. The id is lower case letters, digits and `_`, starting with a letter; the version is `major.minor.patch`; the path must match the `id` and `version` inside the file. Check your file against `schemas/`.
2. A published version never changes: to change an item, add a new version file. Older versions stay readable.
3. Do not reuse the id of a built-in item. The connection type of a template or flow must be built in or in this catalog.
4. Optionally add a `README.md` next to the version files: setup steps and anything a user should know. Keep the JSON `description` to one line.
5. From the repo root, regenerate the derived files and check everything:

```
uv --directory api run python -m scripts.build_catalog_index
uv --directory api run python -m scripts.export_connection_type_schema
uv --directory api run python -m scripts.export_node_template_schema
uv --directory api run python -m scripts.export_flow_schema
make check-marketplace
```

### Flows

A flow file holds `id`, `version`, `name`, `description`, `tags`, a `draft` (the same graph a `.flow.json` file holds) and `connections`. A request node that signs its request with a connection sets `connection_id` to a UUID of your choosing, and `connections` maps each such UUID to `{ "type": ..., "name": ... }`, the connection type it needs and the name to suggest. Every UUID a node uses must be declared and every declared one must be used. The installer picks their own connection for each when they start a flow from it, so no credential or host is ever in the file.

A flow must be a valid graph and must not contain subflow nodes, because a subflow points at a flow of the installer's own workspace.

Pull requests that touch this folder run `check-marketplace` in CI. It loads every file with the app's own loaders, checks paths, ids and requirements, caps file sizes, and fails when `index.json` or `schemas/` are out of date. Files must stay under 256 KB.

## Nightly health

Every night the `health` job in `.github/workflows/docs.yml` reads the published catalog from `main` the way an installing server does, using the app's own loaders. For each item it checks that every listed file exists, matches the hash in `index.json`, and is still readable by the current version of the app, and that a listed `README.md` can be read. A template also fails when a type it needs is failing. The result is `health.json`, published with the docs site at `/health.json`. Nothing is committed to the repository.

An item that fails two nights in a row is `broken`: the Marketplace shows a badge and pauses installing and updating it. Passing once clears it. A red workflow run is the alert. To fix a broken item, add a new version file (a published version never changes). Run the check yourself with:

```
uv --directory api run python -m scripts.check_catalog_health --catalog-url marketplace --out health.json
```

Merging to `main` publishes the change: apps pick it up when their cached index expires (5 minutes), and the docs catalog pages are rebuilt.

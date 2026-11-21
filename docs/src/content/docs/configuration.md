---
title: "Configuration"
---

Settings are environment variables, read once at start. Copy `.env.example` to `.env` and set the few it lists; everything else has a default that suits a normal self-hosted install. A shared public deployment tightens the defaults through the environment; [`.env.limited.example`](https://github.com/ShanuDey/decision-flow/blob/main/.env.limited.example) is the set the public demo uses.

| Area | Page |
|---|---|
| Caps, timeouts, rate limits, the notice on limit errors | [limits](limits) |
| Deleting flows and old versions: `DELETE_MODE` | [data deletion](data-deletion) |
| Deleting old runs and inactive users | [retention](retention) |
| Sign-in methods, token issuers, allowed email domains | [auth](auth) |
| Stored secrets and the key that encrypts them: `ENCRYPTION_KEY` | [secrets](secrets) |
| Which addresses flows may call, and how large and slow a call may be | [HTTP Request](nodes/http-request) |

Other settings:

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | local Postgres | The app database |
| `CORS_ORIGINS` | `http://localhost:3000` | Web origins allowed to call the API, comma separated. `*` is refused |
| `MLFLOW_TRACKING_URI` | the app database, schema `mlflow` | Where run traces go |
| `MLFLOW_SET_EXPERIMENT` | `decision-flow` | MLflow experiment name |
| `CATALOG_URL` | this project's `marketplace` folder on GitHub (`main`) | Where the [Marketplace](marketplace#where-the-list-comes-from) list is read from. See below |
| `API_DOCS_ENABLED` | `false` | Serves `/docs`, `/redoc` and `/openapi.json`. Leave off when deployed |

## Marketplace source

`CATALOG_URL` is the address of a `marketplace` folder: an `https://` URL that serves `index.json` and `catalog/...` files, or a path to a folder on the server. The default is the public repository on GitHub.

- A **fork or mirror** gives you a private or reviewed catalog. Point `CATALOG_URL` at it.
- A **folder path** reads the files from disk, which works offline and in tests.
- **Empty** switches the Marketplace off. The page says it is unavailable; built-in items and anything already installed keep working.
- To keep a list from changing under you, point at a tag or a commit of the repository instead of `main`.

The server fetches the list when someone opens the Marketplace and keeps it for 5 minutes. If a refresh fails it shows the last copy and says so. Installing fetches one file of at most 256 KB, over https, with a 5 second limit and no redirects, and checks it against the hash in the list. Only the Marketplace page and installing need the catalog to be reachable; running flows never do.

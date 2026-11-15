---
title: "Configuration"
---

Settings are environment variables, read once at start. Copy `.env.example` to `.env` and set the few it lists; everything else has a default that suits a normal self-hosted install. A shared public deployment tightens the defaults through the environment; [`.env.limited.example`](https://github.com/ShanuDey/decision-flow/blob/main/.env.limited.example) is the set the public demo uses.

| Area | Page |
|---|---|
| Caps, timeouts, rate limits, the notice on limit errors | [limits](/docs/limits) |
| Deleting flows and old versions: `DELETE_MODE` | [data deletion](/docs/data-deletion) |
| Deleting old runs and inactive users | [retention](/docs/retention) |
| Sign-in methods, token issuers, allowed email domains | [auth](/docs/auth) |

Other settings:

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | local Postgres | The app database |
| `CORS_ORIGINS` | `http://localhost:3000` | Web origins allowed to call the API, comma separated. `*` is refused |
| `MLFLOW_TRACKING_URI` | the app database, schema `mlflow` | Where run traces go |
| `MLFLOW_SET_EXPERIMENT` | `decision-flow` | MLflow experiment name |
| `API_DOCS_ENABLED` | `false` | Serves `/docs`, `/redoc` and `/openapi.json`. Leave off when deployed |

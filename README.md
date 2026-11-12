# decision-flow

A visual editor for building decision flows as graphs, plus an API that runs them and records every run as a trace.

See [docs/](docs/README.md) for concepts and node reference.

## Quick start

Needs Docker with Compose v2 (`docker compose`).

```bash
curl -O https://raw.githubusercontent.com/ShanuDey/decision-flow/main/docker-compose.yml
echo "POSTGRES_PASSWORD=$(openssl rand -hex 16)" > .env
docker compose up -d
```

Open http://localhost:3000 (system status at `/status`).

Set these in `.env` to change the defaults:

| Variable | Default | |
|---|---|---|
| `POSTGRES_PASSWORD` | none | Required. Letters and digits only. |
| `APP_VERSION` | `latest` | Image tag to run. |
| `WEB_URL` | `http://localhost:3000` | Address you open in the browser. |
| `MLFLOW_TRACKING_URI` | the bundled Postgres, schema `mlflow` | Optional. Traces go to the app database by default. Set it to use an MLflow server or another database instead; for the app database add `?options=-csearch_path%3Dmlflow`. |
| `MLFLOW_SET_EXPERIMENT` | `decision-flow` | MLflow experiment that holds run traces. |
| `WEB_PORT`, `API_PORT` | `3000`, `8000` | Published ports. |

Hosting notes:

- **Managed Postgres:** if the provider offers pooled and direct connection strings, use the direct one for `DATABASE_URL`. Pooled (PgBouncer) hosts reject the `options` parameter MLflow needs, and the API then logs why tracing is off.
- **Health checks:** point platform probes at `/health`. `/ready` also checks the database and tracing, so it can return 503 for a few seconds after start, and polling it keeps a sleeping database awake.
- **Upgrading:** the MLflow server container is gone. Delete `MLFLOW_TRACKING_URI=http://...` and `MLFLOW_PORT` from `.env`, or traces stay off and `/ready` stays 503. Earlier traces remain in the old `mlflow` database.

## Development

Needs Docker, [uv](https://docs.astral.sh/uv/), and Node with pnpm.

```bash
make start    # Postgres and Adminer in Docker; API on :8000 and web on :3000 with hot reload
make up       # or run everything from source in Docker
make mlflow-ui  # view run traces at http://127.0.0.1:5000 (there is no MLflow server container)
make checks   # lint, format, tests, type check, API client check
```

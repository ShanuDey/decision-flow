# decision-flow

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
| `MLFLOW_SET_EXPERIMENT` | `decision-flow` | MLflow experiment that holds run traces. |
| `WEB_PORT`, `API_PORT`, `MLFLOW_PORT` | `3000`, `8000`, `5000` | Published ports. MLflow listens on localhost only. |

## Development

Needs Docker, [uv](https://docs.astral.sh/uv/), and Node with pnpm.

```bash
make start    # Postgres, MLflow and Adminer in Docker; API on :8000 and web on :3000 with hot reload
make up       # or run everything from source in Docker
make checks   # lint, format, tests, type check, API client check
```

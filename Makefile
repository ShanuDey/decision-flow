API := uv --directory api run
COMPOSE := docker compose -f docker-compose.dev.yml
WEB := pnpm --dir web
STUDIO_PORT ?= 2024
MLFLOW_UI_PORT ?= 5000

.PHONY: start api studio kill-studio kill-port web db mlflow-ui adminer up down migrate migration db-reset openapi client client-check \
	lint lint-api lint-web lint-fix lint-fix-api lint-fix-web format-api format-check-api fix \
	test-api test-api-fast typecheck-web build-web checks

# containers first (detached), then both dev servers in parallel; Ctrl+C stops only the servers
start: db adminer
	$(MAKE) -j2 api web

api: migrate
	$(API) fastapi dev

studio:
	$(API) langgraph dev --port $(STUDIO_PORT) $(ARGS)

kill-studio:
	@$(MAKE) --no-print-directory kill-port PORT=$(STUDIO_PORT)

kill-port:
	@[ -n "$(PORT)" ] || { echo "usage: make kill-port PORT=<port>"; exit 1; }
	$(WEB) dlx kill-port $(PORT)

web:
	$(WEB) dev

db:
	$(COMPOSE) up -d --wait db

# view-only: opens the same database URI the API derives
mlflow-ui:
	@uri=$$($(API) python -c "from app.settings import get_settings; print(get_settings().mlflow_tracking_uri)") && \
	MLFLOW_BACKEND_STORE_URI="$$uri" uv run --no-project \
		--with "mlflow==3.18.0" --with "psycopg[binary]" \
		mlflow ui --host 127.0.0.1 --port $(MLFLOW_UI_PORT)

adminer:
	$(COMPOSE) --profile tools up -d adminer

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) --profile "*" down

migrate:
	$(API) alembic upgrade head

# usage: make migration m="add flows table"
migration:
	$(API) alembic revision --autogenerate -m "$(m)"

# destructive: deletes all local database data
db-reset:
	$(COMPOSE) --profile "*" down -v
	$(COMPOSE) up -d db

openapi:
	$(API) python -m scripts.export_openapi

client: openapi
	pnpm --dir web generate

# fails if the committed client does not match the current API schema
client-check:
	@sig() { cat api/openapi.json $$(find web/src/lib/api -type f | sort) | cksum; }; \
	before=$$(sig); \
	$(MAKE) --no-print-directory client >/dev/null; \
	[ "$$before" = "$$(sig)" ] || { echo "API client out of date: files regenerated, review and commit"; exit 1; }

lint-api:
	$(API) ruff check .

lint-web:
	$(WEB) lint

lint: lint-api lint-web

lint-fix-api:
	$(API) ruff check --fix .

lint-fix-web:
	$(WEB) lint --fix

lint-fix: lint-fix-api lint-fix-web

format-api:
	$(API) ruff format .

format-check-api:
	$(API) ruff format --check .

fix: lint-fix format-api

test-api:
	$(API) pytest

# skips the Postgres tests that need Docker (Testcontainers)
test-api-fast:
	$(API) pytest -m "not db"

# typegen creates the global route types (LayoutProps, ...) that a clean checkout lacks
typecheck-web:
	$(WEB) exec next typegen
	$(WEB) exec tsc --noEmit

# slow, and writes to web/.next (clashes with a running dev server): not part of checks
build-web:
	$(WEB) build

checks: lint format-check-api test-api typecheck-web client-check

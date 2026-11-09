API := uv --directory api run

.PHONY: api db mlflow adminer up down migrate migration db-reset openapi client client-check lint lint-fix format-check format fix test checks

api: migrate
	$(API) fastapi dev

db:
	docker compose up -d db

mlflow:
	docker compose up -d mlflow

adminer:
	docker compose --profile tools up -d adminer

up:
	docker compose up -d --build

down:
	docker compose --profile "*" down

migrate:
	$(API) alembic upgrade head

# usage: make migration m="add flows table"
migration:
	$(API) alembic revision --autogenerate -m "$(m)"

# destructive: deletes all local database data
db-reset:
	docker compose --profile "*" down -v
	docker compose up -d db

openapi:
	$(API) python -m scripts.export_openapi

# regenerate the web API client from the API's OpenAPI schema
client: openapi
	pnpm --dir web generate

# fails if the committed client does not match the current API schema
client-check:
	@sig() { cat api/openapi.json $$(find web/src/lib/api -type f | sort) | cksum; }; \
	before=$$(sig); \
	$(MAKE) --no-print-directory client >/dev/null; \
	[ "$$before" = "$$(sig)" ] || { echo "API client out of date: files regenerated, review and commit"; exit 1; }

lint:
	$(API) ruff check .

lint-fix:
	$(API) ruff check --fix .

format-check:
	$(API) ruff format --check .

format:
	$(API) ruff format .

fix: lint-fix format

test:
	$(API) pytest

checks: lint format-check test client-check

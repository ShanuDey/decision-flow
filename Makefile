API := uv --directory api run
WEB := pnpm --dir web

.PHONY: api db mlflow adminer up down migrate migration db-reset openapi client client-check \
	lint lint-api lint-web lint-fix lint-fix-api lint-fix-web format-api format-check-api fix \
	test-api typecheck-web build-web checks

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

typecheck-web:
	$(WEB) exec tsc --noEmit

# slow, and writes to web/.next (clashes with a running dev server): not part of checks
build-web:
	$(WEB) build

checks: lint format-check-api test-api typecheck-web client-check

API := uv --directory api run

.PHONY: start db adminer up down migrate migration db-reset lint lint-fix format-check format fix test checks

start: migrate
	$(API) fastapi dev

db:
	docker compose up -d db

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

checks: lint format-check test

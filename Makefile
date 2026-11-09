API := uv --directory api run

.PHONY: start db up down migrate migration db-reset lint lint-fix format-check format fix test checks

start: migrate
	$(API) fastapi dev

db:
	docker compose up -d db

up:
	docker compose up -d --build

down:
	docker compose down

migrate:
	$(API) alembic upgrade head

# usage: make migration m="add flows table"
migration:
	$(API) alembic revision --autogenerate -m "$(m)"

# destructive: deletes all local database data
db-reset:
	docker compose down -v
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

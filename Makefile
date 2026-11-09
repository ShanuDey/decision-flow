API := uv --directory api run

.PHONY: start lint lint-fix format-check format fix test checks

start:
	$(API) fastapi dev

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

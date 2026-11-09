API := uv --directory api run

.PHONY: start lint format fix checks

start:
	$(API) fastapi dev

lint:
	$(API) ruff check .

format:
	$(API) ruff format .

fix:
	$(API) ruff check --fix .
	$(API) ruff format .

checks:
	$(API) ruff check .
	$(API) ruff format --check .
	$(API) pytest -q

.PHONY: test lint typecheck check format all

all: lint typecheck test

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy --config-file pyproject.toml .

test:
	pytest -v tests/

check: lint typecheck test

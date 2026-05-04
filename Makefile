.PHONY: check lint typecheck test fix

check: lint typecheck test

lint:
	uv run ruff check src/ tests/

typecheck:
	uv run mypy src/

test:
	uv run pytest

fix:
	uv run ruff check --fix src/ tests/

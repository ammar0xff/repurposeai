.PHONY: install dev test lint format typecheck build clean doctor
install: ; pip install -e ".[dev]"
dev: ; uvicorn app.main:app --reload --port $${PORT:-8000}
test: ; pytest -q
lint: ; ruff check app tests scripts
format: ; ruff format app tests scripts
typecheck: ; mypy app
build: ; docker compose build
clean: ; rm -rf data/* .pytest_cache .ruff_cache .mypy_cache
doctor: ; python -m app.cli doctor

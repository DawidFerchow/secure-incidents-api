.PHONY: install check test audit run up down logs smoke

install:
	uv sync --frozen --all-groups

check:
	uv run ruff format --check .
	uv run ruff check .

test:
	uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=80

audit:
	uv run bandit -q -r app
	uv run pip-audit

run:
	uv run uvicorn app.main:app --host 127.0.0.1 --port 8080 --no-access-log

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f app alloy loki grafana

smoke:
	uv run python tests/smoke_test.py

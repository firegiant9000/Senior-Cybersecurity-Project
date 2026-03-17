.PHONY: help up down logs backend-test backend-lint migrate makemigrations rollback seed

help:
	@echo "Available commands:"
	@echo "  make up                - Start Docker services"
	@echo "  make down              - Stop Docker services"
	@echo "  make logs              - View Docker logs (all services)"
	@echo "  make backend-logs      - View backend logs"
	@echo "  make migrate           - Run database migrations"
	@echo "  make makemigrations    - Create new migration (use with message=...)"
	@echo "  make rollback          - Rollback the last migration"
	@echo "  make seed              - Seed database with sample data (TODO)"
	@echo "  make backend-test      - Run backend tests"
	@echo "  make backend-lint      - Lint backend code with ruff"
	@echo "  make frontend-install  - Install frontend dependencies"
	@echo "  make frontend-lint     - Lint frontend code"

up:
	docker compose up -d
	@echo "Services started. Backend: http://localhost:8000, Frontend: http://localhost:5173"

down:
	docker compose down

logs:
	docker compose logs -f

backend-logs:
	docker compose logs -f backend

frontend-logs:
	docker compose logs -f frontend

migrate:
	docker compose exec backend alembic -c app/db/alembic.ini upgrade head

makemigrations:
	@if [ -z "$(message)" ]; then \
		echo "Usage: make makemigrations message=\"your message\""; \
		exit 1; \
	fi
	docker compose exec backend alembic -c app/db/alembic.ini revision --autogenerate -m "$(message)"

rollback:
	docker compose exec backend alembic -c app/db/alembic.ini downgrade -1

seed:
	@echo "TODO: Implement database seeding"
	@docker compose exec backend python -m app.scripts.seed

backend-test:
	docker compose exec backend pytest -v tests/

backend-lint:
	docker compose exec backend ruff check app tests
	docker compose exec backend ruff format app tests --check

backend-format:
	docker compose exec backend ruff format app tests

frontend-install:
	cd frontend && npm install

frontend-lint:
	cd frontend && npm run lint

frontend-format:
	cd frontend && npm run format

# Local development (without Docker)
venv:
	python -m venv backend/venv
	@echo "Virtual environment created. Activate with: source backend/venv/bin/activate"

install-local:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

migrate-local:
	cd backend && alembic upgrade head

test-local:
	cd backend && pytest -v tests/

lint-local:
	cd backend && ruff check app tests

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	find frontend -type d -name node_modules -exec rm -rf {} +
	find frontend -type d -name dist -exec rm -rf {} +

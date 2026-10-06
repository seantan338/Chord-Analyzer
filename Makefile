# Convenience commands. Run `make help`.
.PHONY: help install dev-backend dev-frontend check check-backend check-frontend demo-audio types up

help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-16s %s\n", $$1, $$2}'

install: ## Create backend venv and install all dependencies
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
	cd frontend && npm ci

dev-backend: ## Run the API with auto-reload on :8000
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

dev-frontend: ## Run the web app on :3000
	cd frontend && npm run dev

check: check-backend check-frontend ## Lint, typecheck, test and build everything

check-backend: ## ruff + mypy + pytest
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app && .venv/bin/pytest

check-frontend: ## eslint + prettier + tsc + vitest + next build
	cd frontend && npm run check

types: ## Regenerate docs/openapi.json and frontend TypeScript types
	cd backend && .venv/bin/python -m scripts.export_openapi
	cd frontend && npm run gen:api

demo-audio: ## Render a synthetic demo song (demo-song.wav/.mp3)
	cd backend && .venv/bin/python -m scripts.make_demo_audio ../demo-song.wav

up: ## Build and start the Docker stack
	docker compose up --build

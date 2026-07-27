.PHONY: help up down logs seed test lint fmt migrate shell eval

help:
	@grep -E '^[a-z-]+:.*?##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/'

up: ## Build and start the whole stack
	cp -n .env.example .env || true
	docker compose up --build -d
	@echo "API   http://localhost:8000/api/docs/"
	@echo "Web   http://localhost:3000"

down: ## Stop everything
	docker compose down

logs: ## Tail all logs
	docker compose logs -f --tail=100

migrate: ## Apply migrations
	docker compose exec api python manage.py makemigrations tickets
	docker compose exec api python manage.py migrate

seed: ## Load both datasets and build the vector index (~6 min first run)
	docker compose exec api python scripts/ingest_tickets.py --limit 8000
	docker compose exec api python scripts/build_kb.py --per-intent 40

eval: ## Score the triage model on a held-out sample
	docker compose exec api python scripts/evaluate_triage.py --sample 1500

test: ## Run the backend test suite with coverage
	docker compose exec -e LLM_PROVIDER=echo api pytest

lint: ## Ruff + eslint
	docker compose exec api ruff check apps scripts
	cd frontend && npm run lint

fmt:
	docker compose exec api ruff format apps scripts

shell:
	docker compose exec api python manage.py shell

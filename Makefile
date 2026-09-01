.PHONY: help dev up down logs db-migrate db-upgrade db-revision test lint clean

# ── Default ─────────────────────────────────────────────────
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Development ─────────────────────────────────────────────
dev: ## Run API locally with hot-reload (requires running `make up` first)
	uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload

up: ## Start all services with Docker Compose
	docker compose up -d
	@echo "Services starting... API at http://localhost:8000"
	@echo "MinIO Console at http://localhost:9001"

down: ## Stop all services
	docker compose down

logs: ## Tail logs from all services
	docker compose logs -f

logs-api: ## Tail API logs only
	docker compose logs -f api

# ── Database ────────────────────────────────────────────────
db-shell: ## Open psql shell to the database
	docker compose exec db psql -U market -d market_platform

db-migrate: ## Generate a new Alembic migration
	alembic revision --autogenerate -m "$(msg)"

db-upgrade: ## Apply all pending migrations
	alembic upgrade head

db-downgrade: ## Rollback one migration
	alembic downgrade -1

db-history: ## Show migration history
	alembic history

# ── Testing ─────────────────────────────────────────────────
test: ## Run all tests
	pytest tests/ -v --tb=short

test-unit: ## Run unit tests only
	pytest tests/unit/ -v --tb=short -m unit

test-integration: ## Run integration tests only
	pytest tests/integration/ -v --tb=short -m integration

test-golden: ## Run golden/backtest reproducibility tests
	pytest tests/golden/ -v --tb=short -m golden

test-cov: ## Run tests with coverage
	pytest tests/ -v --cov=apps --cov=packages --cov-report=term-missing

# ── Code Quality ────────────────────────────────────────────
lint: ## Run linter (ruff)
	ruff check apps/ packages/ tests/

lint-fix: ## Auto-fix lint issues
	ruff check --fix apps/ packages/ tests/

format: ## Format code
	ruff format apps/ packages/ tests/

typecheck: ## Run type checking (mypy)
	mypy apps/ packages/

# ── Cleanup ─────────────────────────────────────────────────
clean: ## Remove caches, build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache .ruff_cache dist build

clean-all: clean down ## Full cleanup including Docker volumes
	docker compose down -v

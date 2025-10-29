# Variables
PYTHON := python3
UV := uv
PYTEST := pytest
RUFF := ruff

# Default target
.PHONY: help
help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Install dependencies
	@if [ ! -f .env ]; then \
		echo "Creating .env file from .env.example..."; \
		cp .env.example .env; \
		echo "⚠️  Please update .env with your local configuration"; \
	fi
	$(UV) sync --dev

.PHONY: install-prod
install-prod: ## Install production dependencies only
	$(UV) sync

.PHONY: clean
clean: ## Clean up generated files
	rm -rf __pycache__
	rm -rf */__pycache__
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -rf .coverage
	find . -type d -name '.mypy_cache' -exec rm -rf {} +
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

.PHONY: lint
lint: ## Run linting with Ruff
	$(UV) run $(RUFF) check .

.PHONY: lint-fix
lint-fix: ## Run linting with Ruff and fix issues
	$(UV) run $(RUFF) check . --fix

.PHONY: format
format: ## Format code with Ruff
	$(UV) run $(RUFF) format .

.PHONY: check
check: lint ## Run all checks (linting, etc.)

.PHONY: test
test: ## Run tests
	$(UV) run $(PYTEST) tests/ -v

.PHONY: test-cov
test-cov: ## Run tests with coverage
	$(UV) run $(PYTEST) tests/ --cov=app --cov-report=html --cov-report=term-missing

.PHONY: test-watch
test-watch: ## Run tests in watch mode
	$(UV) run pytest-watch tests/ -v

.PHONY: dev
dev: install ## Start backend in development mode
	@echo "Starting backend development server..."
	$(UV) run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: run
run: ## Run development server
	$(UV) run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: run-prod
run-prod: ## Run production server
	$(UV) run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

.PHONY: build
build: ## Build Docker image
	@echo "Building Docker image..."
	docker build -t co2-calculator-backend .
	@echo "Docker image built!"

# =============================================================================
# Database
# =============================================================================

.PHONY: init-db
init-db: ## Initialize database (development only)
	@echo "Initializing database..."
	$(UV) run python -c "from app.db import init_db; init_db()"
	@echo "Database initialized!"

.PHONY: db-migrate
db-migrate: ## Run database migrations (upgrade to head)
	@echo "Running database migrations..."
	$(UV) run alembic upgrade head

.PHONY: db-revision
db-revision: ## Create new migration (usage: make db-revision message="description")
	@echo "Creating new migration..."
	$(UV) run alembic revision --autogenerate -m "$(message)"

.PHONY: db-downgrade
db-downgrade: ## Downgrade database by one revision
	@echo "Downgrading database..."
	$(UV) run alembic downgrade -1

.PHONY: db-seed
db-seed: ## Seed database with sample data
	@echo "Seeding database..."
	$(UV) run python scripts/seed.py

.PHONY: db-reset
db-reset: ## Reset database (drop + migrate + seed)
	@echo "Resetting database..."
	$(UV) run alembic downgrade base
	$(UV) run alembic upgrade head
	$(UV) run python scripts/seed.py
	@echo "Database reset complete!"

.PHONY: db-shell
db-shell: ## Open database shell
	@echo "Opening database shell..."
	$(UV) run python scripts/db_shell.py

# =============================================================================
# Docker
# =============================================================================

.PHONY: docker-up
docker-up: ## Start Docker Compose services
	@echo "Starting Docker services..."
	docker-compose up -d
	@echo "Docker services started!"

.PHONY: docker-down
docker-down: ## Stop Docker Compose services
	@echo "Stopping Docker services..."
	docker-compose down
	@echo "Docker services stopped!"

.PHONY: docker-logs
docker-logs: ## View Docker Compose logs
	docker-compose logs -f

.PHONY: docker-shell
docker-shell: ## Open shell in backend container
	docker-compose exec backend bash

# =============================================================================
# OPA
# =============================================================================

.PHONY: opa-test
opa-test: ## Test OPA policies
	@echo "Testing OPA policies..."
	opa test app/policies/
	@echo "OPA policy tests complete!"

.PHONY: opa-run
opa-run: ## Run OPA server locally
	@echo "Starting OPA server..."
	opa run --server --addr :8181 app/policies/

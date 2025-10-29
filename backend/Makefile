.PHONY: help install clean dev build test test-watch format format-check lint
.PHONY: db-migrate db-seed db-reset db-shell

help: ## Show this help message
	@echo "Backend Makefile targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install backend dependencies
	@echo "Installing backend dependencies..."
	uv sync
	@echo "Backend dependencies installed!"

clean: ## Clean backend dependencies and build artifacts
	@echo "Cleaning backend..."
	rm -rf .venv __pycache__ .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Backend cleaned!"

dev: ## Start backend in development mode
	@echo "Starting backend development server..."
	uv run uvicorn main:app --reload

build: ## Build backend (if applicable)
	@echo "Building backend..."
	@echo "Backend build complete (nothing to build for Python)!"

test: ## Run backend tests
	@echo "Running backend tests..."
	uv run pytest

test-watch: ## Run backend tests in watch mode
	@echo "Running backend tests in watch mode..."
	uv run pytest-watch

format: ## Format backend code
	@echo "Formatting backend code..."
	uv run ruff format .
	uv run ruff check . --fix
	@echo "Backend formatting complete!"

format-check: ## Check backend code formatting
	@echo "Checking backend formatting..."
	uv run ruff format --check .
	uv run ruff check .
	@echo "Backend format check complete!"

lint: ## Lint backend code
	@echo "Linting backend code..."
	uv run ruff check .
	@echo "Backend linting complete!"

# =============================================================================
# Database
# =============================================================================

db-migrate: ## Run database migrations
	@echo "Running database migrations..."
	uv run alembic upgrade head

db-seed: ## Seed database with sample data
	@echo "Seeding database..."
	uv run python scripts/seed.py

db-reset: ## Reset database (drop + migrate + seed)
	@echo "Resetting database..."
	uv run alembic downgrade base
	uv run alembic upgrade head
	uv run python scripts/seed.py
	@echo "Database reset complete!"

db-shell: ## Open database shell
	@echo "Opening database shell..."
	uv run python scripts/db_shell.py

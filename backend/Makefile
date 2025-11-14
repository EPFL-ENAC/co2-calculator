# Variables
PYTHON := python3
UV := uv
RUFF ?= $(UV) run ruff
PYTEST ?= $(UV) run pytest


.PHONY: help
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Install dependencies
	@if [ ! -f .env ]; then \
		echo "Creating .env from .env.example..."; \
		cp .env.example .env; \
		echo "⚠️  Update .env with your configuration"; \
	fi
	uv sync --dev

.PHONY: install-prod
install-prod: ## Install production dependencies only
	uv sync

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

# FILES can be overridden to target specific files (for git hooks)
FILES ?= .

# File filters
PY_FILES   := $(filter %.py,$(FILES))
YAML_FILES := $(filter %.yml %.yaml,$(FILES))
MD_FILES   := $(filter %.md,$(FILES))


# =============================================================================
# Development Tasks
# =============================================================================
.PHONY: format
format: ## Format code with ruff and prettier
	@if [ -n "$(PY_FILES)" ]; then \
		ruff format $(PY_FILES); \
		ruff check --fix $(PY_FILES); \
	fi
	@if [ -n "$(YAML_FILES)" ] || [ -n "$(MD_FILES)" ]; then \
		npx prettier --write $(YAML_FILES) $(MD_FILES) --ignore-unknown; \
	fi

.PHONY: lint
lint: ## Check code formatting
	@if [ -n "$(PY_FILES)" ]; then \
		ruff format --check $(PY_FILES); \
		ruff check $(PY_FILES); \
	fi
	@if [ -n "$(YAML_FILES)" ] || [ -n "$(MD_FILES)" ]; then \
		npx prettier --check $(YAML_FILES) $(MD_FILES) --ignore-unknown; \
	fi

.PHONY: type-check
type-check: ## Run type checking with mypy
	uv run mypy app/

.PHONY: test
test: ## Run tests
	uv run pytest tests/ -v

.PHONY: test-cov
test-cov: ## Run tests with coverage
	uv run pytest tests/ --cov=app --cov-report=html --cov-report=term-missing

.PHONY: dev
dev: install ## Start backend development server
	@if [ ! -f .env ]; then \
		echo "❌ .env not found! Creating from .env.example..."; \
		cp .env.example .env; \
		echo "⚠️  Update .env with your configuration"; \
		exit 1; \
	fi
	@echo "Starting backend development server..."
	$(UV) run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: dev
run: dev ## Alias for dev

.PHONY: run-prod
run-prod: ## Run production server
	$(UV) run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

.PHONY: build
build: ## Build Docker image
	docker build -t co2-calculator-backend .

# =============================================================================
# Database
# =============================================================================

.PHONY: db-migrate
db-migrate: ## Run database migrations (upgrade to head)
	uv run alembic upgrade head

.PHONY: db-revision
db-revision: ## Create new migration (usage: make db-revision message="description")
	uv run alembic revision --autogenerate -m "$(message)"


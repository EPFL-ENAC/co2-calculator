.PHONY: help install clean uninstall
.PHONY: up down restart logs ps
.PHONY: dev dev-backend dev-frontend
.PHONY: build build-backend build-frontend
.PHONY: test test-backend test-frontend test-watch
.PHONY: db-migrate db-seed db-reset db-shell
.PHONY: shell-backend shell-frontend prune reset
.PHONY: ci format format-check lint
.PHONY: pdf build-docs serve-docs

# Default target
help: ## Show this help message
	@echo "Available targets:"
	@echo ""
	@echo "Docker & Services:"
	@grep -E '^(up|down|restart|logs|ps):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Development:"
	@grep -E '^(dev|dev-backend|dev-frontend):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Building:"
	@grep -E '^(build|build-backend|build-frontend):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Testing:"
	@grep -E '^(test|test-backend|test-frontend|test-watch):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Database:"
	@grep -E '^(db-migrate|db-seed|db-reset|db-shell):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Utilities:"
	@grep -E '^(shell-backend|shell-frontend|prune|reset|clean|install|uninstall):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "CI/CD:"
	@grep -E '^(ci|format|format-check|lint):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Documentation:"
	@grep -E '^(pdf|build-docs|serve-docs):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# =============================================================================
# Docker & Services
# =============================================================================

up: ## Start all services (docker-compose up)
	@echo "Starting all services..."
	docker-compose up -d
	@echo "Services started!"

down: ## Stop all services (docker-compose down)
	@echo "Stopping all services..."
	docker-compose down
	@echo "Services stopped!"

restart: ## Restart all services
	@echo "Restarting all services..."
	docker-compose restart
	@echo "Services restarted!"

logs: ## View logs from all services
	docker-compose logs -f

ps: ## Show running containers status
	docker-compose ps

# =============================================================================
# Development
# =============================================================================

dev: ## Start development environment (up + watch mode)
	@echo "Starting development environment..."
	docker-compose up

dev-backend: ## Run only backend in dev mode
	@echo "Starting backend in development mode..."
	cd backend && $(MAKE) dev

dev-frontend: ## Run only frontend in dev mode
	@echo "Starting frontend in development mode..."
	cd frontend && $(MAKE) dev

# =============================================================================
# Building
# =============================================================================

build: build-backend build-frontend ## Build all projects (frontend + backend)
	@echo "All builds complete!"

build-backend: ## Build backend only
	@echo "Building backend..."
	cd backend && $(MAKE) build

build-frontend: ## Build frontend only
	@echo "Building frontend..."
	cd frontend && $(MAKE) build

# =============================================================================
# Testing
# =============================================================================

test: test-backend test-frontend ## Run all tests (frontend + backend)
	@echo "All tests complete!"

test-backend: ## Run backend tests
	@echo "Running backend tests..."
	cd backend && $(MAKE) test

test-frontend: ## Run frontend tests
	@echo "Running frontend tests..."
	cd frontend && $(MAKE) test

test-watch: ## Run tests in watch mode
	@echo "Running tests in watch mode..."
	@echo "Backend tests in watch mode:"
	cd backend && $(MAKE) test-watch &
	@echo "Frontend tests in watch mode:"
	cd frontend && $(MAKE) test-watch

# =============================================================================
# Database
# =============================================================================

db-migrate: ## Run database migrations
	@echo "Running database migrations..."
	cd backend && $(MAKE) db-migrate

db-seed: ## Seed database with sample data
	@echo "Seeding database..."
	cd backend && $(MAKE) db-seed

db-reset: ## Reset database (drop + migrate + seed)
	@echo "Resetting database..."
	cd backend && $(MAKE) db-reset

db-shell: ## Open database shell
	@echo "Opening database shell..."
	cd backend && $(MAKE) db-shell

# =============================================================================
# Utilities
# =============================================================================

shell-backend: ## Open shell in backend container
	docker-compose exec backend /bin/bash

shell-frontend: ## Open shell in frontend container
	docker-compose exec frontend /bin/sh

prune: ## Clean docker volumes/images
	@echo "Cleaning docker volumes and images..."
	docker-compose down -v
	docker system prune -f
	@echo "Docker cleanup complete!"

reset: down clean install up ## Nuclear option (down + clean + install + up)
	@echo "Reset complete!"

install: ## Install npm dependencies and set up git hooks
	@echo "Installing npm dependencies..."
	npm install
	@echo "Syncing uv environment..."
	uv sync
	@echo "Installing git hooks with lefthook..."
	npx lefthook install
	@echo "Installing backend dependencies..."
	cd backend && $(MAKE) install
	@echo "Installing frontend dependencies..."
	cd frontend && $(MAKE) install
	@echo "Setup complete!"

clean: ## Remove node_modules and package-lock.json
	@echo "Cleaning dependencies..."
	rm -rf node_modules
	rm -f package-lock.json
	cd backend && $(MAKE) clean
	cd frontend && $(MAKE) clean

uninstall: ## Uninstall git hooks and clean dependencies
	@echo "Uninstalling git hooks..."
	npx lefthook uninstall || true
	$(MAKE) clean
	@echo "Uninstall complete!"

# =============================================================================
# CI/CD
# =============================================================================

ci: lint format-check test build ## Run CI checks (lint + format-check + test + build)
	@echo "CI checks complete!"

lint: ## Run linters on the codebase
	@echo "Running linter..."
	LEFTHOOK=0 npx lefthook run pre-commit
	@echo "Linting complete!"

format: ## Format codebase (delegates to frontend and backend)
	@echo "Formatting codebase..."
	@echo "Formatting root Markdown files..."
	npx prettier --write "*.md" --ignore-unknown --ignore-path .prettierignore
	@echo "Formatting backend..."
	cd backend && $(MAKE) format
	@echo "Formatting frontend..."
	cd frontend && $(MAKE) format
	@echo "Formatting complete!"

format-check: ## Check formatting without fixing
	@echo "Checking formatting..."
	npx prettier --check . --ignore-unknown --ignore-path .prettierignore
	cd backend && $(MAKE) format-check
	cd frontend && $(MAKE) format-check
	@echo "Format check complete!"

# =============================================================================
# Documentation
# =============================================================================

pdf: ## Build documentation with PDF export enabled
	UV_NO_ISOLATION=1 ENABLE_PDF_EXPORT=1 uv run mkdocs build

build-docs: ## Build documentation
	UV_NO_ISOLATION=1 uv run mkdocs build

serve-docs: ## Serve documentation with live reload
	mkdocs serve --dirtyreload --watch docs --watch mkdocs.yml

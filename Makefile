.PHONY: help-requirements
help-requirements:
	@echo >&2 "============================================================================="
	@echo >&2 "TOOL REQUIREMENTS"
	@echo >&2 "============================================================================="
	@echo >&2 "Core (always required):"
	@echo >&2 "  make"
	@echo >&2 ""
	@echo >&2 "Backend + Docs:"
	@echo >&2 "  uv  (Python project management)"
	@echo >&2 ""
	@echo >&2 "Frontend + Root:"
	@echo >&2 "  npm (package manager)"
	@echo >&2 "  npx (CLI executor)"
	@echo >&2 ""
	@echo >&2 "Helm (for helm/Makefile only)"
	@echo >&2 "  helm"
	@echo >&2 ""
	@echo >&2 "Docker-related tasks only:"
	@echo >&2 "  docker, docker-compose OR docker compose"
	@echo >&2 ""
	@echo >&2 "Docs (serve/watch only):"
	@echo >&2 "  mkdocs (via uv)"
	@echo >&2 "============================================================================="

HELM_TOOLS := helm

# Detect docker compose command (supports both modern and legacy)
DOCKER_COMPOSE := $(shell command -v docker-compose 2>/dev/null || echo "docker compose")

# Quick prerequisite check utility
define check_tools
	@missing=0; \
	for tool in $(1); do \
		if ! command -v $$tool >/dev/null 2>&1; then \
			echo "❌ Missing tool: $$tool"; \
			missing=1; \
		fi; \
	done; \
	if [ $$missing -eq 1 ]; then \
		echo "⚠️  Missing tools detected. Please install them before continuing."; \
		exit 1; \
	fi
	@echo "✅ All required tools are installed: $(1)"
endef


# example in Makefile:	$(call check_tools,uv npm)

.PHONY: help
# Default target
help: ## Show this help message
	$(MAKE) help-requirements
	@echo "Available targets:"
	@echo ""
	@echo "Docker & Services:"
	@grep -E '^(up|force-up|down|restart|logs|ps):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
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
	@grep -E '^(db-up|db-down|db-restart|db-migrate|db-seed|db-reset|db-shell):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Utilities:"
	@grep -E '^(shell-backend|shell-frontend|prune|reset|clean|install|uninstall):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "CI/CD:"
	@grep -E '^(ci|format|format-root|format-backend|format-frontend|format-docs|format-helm|format-check|format-check-root|format-check-backend|format-check-frontend|format-check-docs|format-check-helm|lint|lint-backend|lint-frontend|lint-docs|lint-helm|type-check|frontend-type-check|backend-type-check):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Documentation:"
	@grep -E '^(pdf|build-docs|serve-docs):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# =============================================================================
# Docker & Services
# =============================================================================

.PHONY: up
up: ## Start all services (docker compose up)
	@echo "Starting all services..."
	docker compose up -d
	@echo "Services started!"

.PHONY: force-up
force-up: down up ## Force restart/rebuild all services
	@echo "Services force restarted!"
	docker compose up -d --build --force-recreate

.PHONY: down
down: ## Stop all services (docker compose down)
	$(call check_tools,docker $(DOCKER_COMPOSE))
	@echo "Stopping all services..."
	docker compose down
	@echo "Services stopped!"

.PHONY: restart
restart: ## Restart all services
	$(call check_tools,docker $(DOCKER_COMPOSE))
	@echo "Restarting all services..."
	docker compose restart
	@echo "Services restarted!"

.PHONY: logs
logs: ## View logs from all services
	$(call check_tools,docker $(DOCKER_COMPOSE))
	docker compose logs -f

.PHONY: ps
ps: ## Show running containers status
	$(call check_tools,docker $(DOCKER_COMPOSE))
	docker compose ps

# =============================================================================
# Development
# =============================================================================

.PHONY: dev
dev: ## Start development environment (up + watch mode)
	@echo "Starting backend and frontend in development mode..."
	@trap 'kill 0' SIGINT; \
	cd backend && $(MAKE) run & \
	cd frontend && $(MAKE) run dev & \
	wait

.PHONY: run
run: db-up dev ## Alias for dev + db up

.PHONY: dev-backend
dev-backend: ## Run only backend in dev mode
	@echo "Starting backend in development mode..."
	@trap 'kill 0' SIGINT; \
	cd backend && $(MAKE) run & \
	wait

.PHONY: dev-frontend
dev-frontend: ## Run only frontend in dev mode
	@echo "Starting frontend in development mode..."
	@trap 'kill 0' SIGINT; \
	cd frontend && $(MAKE) run dev & \
	wait

# =============================================================================
# Building
# =============================================================================

.PHONY: build
build: build-backend build-frontend ## Build all projects (frontend + backend)
	@echo "All builds complete!"

.PHONY: build-backend
build-backend: ## Build backend only
	@echo "Building backend..."
	cd backend && $(MAKE) build

.PHONY: build-frontend
build-frontend: ## Build frontend only
	@echo "Building frontend..."
	cd frontend && $(MAKE) build

# =============================================================================
# Testing
# =============================================================================

.PHONY: test
test: test-backend test-frontend ## Run all tests (frontend + backend)
	@echo "All tests complete!"

.PHONY: test-backend
test-backend: ## Run backend tests
	@echo "Running backend tests..."
	cd backend && $(MAKE) test

.PHONY: test-frontend
test-frontend: ## Run frontend tests
	@echo "Running frontend tests..."
	cd frontend && $(MAKE) test

.PHONY: test-watch
test-watch: ## Run tests in watch mode
	@echo "Running tests in watch mode..."
	@echo "Backend tests in watch mode:"
	cd backend && $(MAKE) test-watch &
	@echo "Frontend tests in watch mode:"
	cd frontend && $(MAKE) test-watch

# =============================================================================
# Database
# =============================================================================

.PHONY: db-up
db-up: ## Start database service
	@echo "Starting database service..."
	docker compose up -d postgres
	@echo "Database service started!"

.PHONY: db-down
db-down: ## Stop database service
	@echo "Stopping database service..."
	docker compose down postgres
	@echo "Database service stopped!"

.PHONY: db-restart
db-restart: ## Restart database service
	@echo "Restarting database service..."
	docker compose restart postgres
	@echo "Database service restarted!"

.PHONY: db-migrate
db-migrate: ## Run database migrations
	@echo "Running database migrations..."
	cd backend && $(MAKE) db-migrate

.PHONY: db-seed
db-seed: ## Seed database with sample data
	@echo "Seeding database..."
	cd backend && $(MAKE) db-seed

.PHONY: db-reset
db-reset: ## Reset database (drop + migrate + seed)
	@echo "Resetting database..."
	cd backend && $(MAKE) db-reset

.PHONY: db-shell
db-shell: ## Open database shell
	@echo "Opening database shell..."
	cd backend && $(MAKE) db-shell

# =============================================================================
# Utilities
# =============================================================================

.PHONY: install
install: ## Install npm dependencies and set up git hooks
	@echo "Installing root npm dependencies... (lefthook will be installed + prettier)"
	npm install
	@echo "Installing git hooks with lefthook..."
	npx lefthook install
	@echo "Installing backend dependencies..."
	cd backend && $(MAKE) install
	@echo "Installing frontend dependencies..."
	cd frontend && $(MAKE) install
	@echo "Installing docs dependencies..."
	cd docs && $(MAKE) install
	@echo "Setup complete!"

.PHONY: clean
clean: ## Remove node_modules and package-lock.json
	@echo "Cleaning dependencies..."
	rm -rf node_modules
	rm -f package-lock.json
	cd backend && $(MAKE) clean
	cd frontend && $(MAKE) clean

.PHONY: uninstall
uninstall: ## Uninstall git hooks and clean dependencies
	@echo "Uninstalling git hooks..."
	npx lefthook uninstall || true
	$(MAKE) clean
	@echo "Uninstall complete!"

# =============================================================================
# CI/CD
# =============================================================================

.PHONY: ci
ci: lint format-check test build ## Run CI checks (lint + format-check + test + build)
	@echo "CI checks complete!"

# Format targets
.PHONY: format format-root format-backend format-frontend format-docs format-helm
format: format-root format-backend format-frontend format-docs format-helm ## Format entire codebase

format-root: ## Format root-level files
	@echo "Formatting root-level files..."
	@npx prettier --write "*.md" "*.json" "*.yml" --ignore-unknown --ignore-path .prettierignore

format-backend: ## Format backend code
	@if [ -d "backend" ]; then \
		cd backend && $(MAKE) format FILES="$(if $(FILES),$(FILES),.)"; \
	else \
		echo "No backend directory found, skipping..."; \
	fi

format-frontend: ## Format frontend code
	@if [ -d "frontend" ]; then \
		cd frontend && $(MAKE) format FILES="$(if $(FILES),$(FILES),.)"; \
	else \
		echo "No frontend directory found, skipping..."; \
	fi

format-docs: ## Format documentation
	@if [ -d "docs" ]; then \
		cd docs && $(MAKE) format FILES="$(if $(FILES),$(FILES),.)"; \
	else \
		echo "No docs directory found, skipping..."; \
	fi

format-helm: ## Format Helm files
	@if [ -d "helm" ]; then \
		cd helm && $(MAKE) format FILES="$(if $(FILES),$(FILES),.)"; \
	else \
		echo "No helm directory found, skipping..."; \
	fi

# Format check targets
.PHONY: format-check format-check-root format-check-backend format-check-frontend format-check-docs format-check-helm
format-check: format-check-root format-check-backend format-check-frontend format-check-docs format-check-helm ## Check formatting

format-check-root: ## Check root-level file formatting
	@echo "Checking root-level file formatting..."
	@npx prettier --check "*.md" "*.json" "*.yml" --ignore-unknown --ignore-path .prettierignore

format-check-backend: ## Check backend formatting
	@if [ -d "backend" ]; then \
		cd backend && $(MAKE) format-check FILES="$(if $(FILES),$(FILES),.)"; \
	else \
		echo "No backend directory found, skipping..."; \
	fi

format-check-frontend: ## Check frontend formatting
	@if [ -d "frontend" ]; then \
		cd frontend && $(MAKE) format-check FILES="$(if $(FILES),$(FILES),.)"; \
	else \
		echo "No frontend directory found, skipping..."; \
	fi

format-check-docs: ## Check documentation formatting
	@if [ -d "docs" ]; then \
		cd docs && $(MAKE) format-check FILES="$(if $(FILES),$(FILES),.)"; \
	else \
		echo "No docs directory found, skipping..."; \
	fi

format-check-helm: ## Check Helm formatting
	@if [ -d "helm" ]; then \
		cd helm && $(MAKE) format-check FILES="$(if $(FILES),$(FILES),.)"; \
	else \
		echo "No helm directory found, skipping..."; \
	fi

# Lint targets
.PHONY: lint lint-backend lint-frontend lint-docs lint-helm
lint: lint-backend lint-frontend lint-docs lint-helm ## Lint entire codebase

lint-backend: ## Lint backend code
	@if [ -d "backend" ]; then \
		cd backend && $(MAKE) lint FILES="$(if $(FILES),$(FILES),.)"; \
	else \
		echo "No backend directory found, skipping..."; \
	fi

lint-frontend: ## Lint frontend code
	@if [ -d "frontend" ]; then \
		cd frontend && $(MAKE) lint FILES="$(if $(FILES),$(FILES),.)"; \
	else \
		echo "No frontend directory found, skipping..."; \
	fi

lint-docs: ## Lint documentation
	@if [ -d "docs" ]; then \
		cd docs && $(MAKE) lint FILES="$(if $(FILES),$(FILES),.)"; \
	else \
		echo "No docs directory found, skipping..."; \
	fi

lint-helm: ## Lint Helm files
	@if [ -d "helm" ]; then \
		cd helm && $(MAKE) lint FILES="$(if $(FILES),$(FILES),.)"; \
	else \
		echo "No helm directory found, skipping..."; \
	fi

.PHONY: type-check frontend-type-check backend-type-check
type-check: frontend-type-check backend-type-check ## Run type checking for frontend and backend

frontend-type-check: ## Run type checking for frontend code
	@echo "Running type checking for frontend..."
	@if [ -d "frontend" ]; then \
		cd frontend && $(MAKE) type-check FILES="$(if $(FILES),$(FILES),.)"; \
	else \
		echo "No frontend directory found, skipping..."; \
	fi

backend-type-check: ## Run type checking for backend code
	@echo "Running type checking for backend..."
	@if [ -d "backend" ]; then \
		cd backend && $(MAKE) type-check FILES="$(if $(FILES),$(FILES),.)"; \
	else \
		echo "No backend directory found, skipping..."; \
	fi

# =============================================================================
# Documentation
# =============================================================================

.PHONY: pdf build-docs serve-docs
pdf: ## Build documentation with PDF export enabled
	UV_NO_ISOLATION=1 ENABLE_PDF_EXPORT=1 uv run mkdocs build

build-docs: ## Build documentation
	UV_NO_ISOLATION=1 uv run mkdocs build

serve-docs: ## Serve documentation with live reload
	mkdocs serve --dirtyreload --watch docs --watch mkdocs.yml

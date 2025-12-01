# =============================================================================
# Root Makefile - CI/CD and Orchestration
# =============================================================================
# This Makefile provides CI validation commands and project-wide orchestration.
# For development workflows, use subfolder Makefiles directly:
#   - Backend: cd backend && make dev
#   - Frontend: cd frontend && make dev
#   - Docs: cd docs && make serve-docs
#
# Root targets are optimized for CI pipelines and pre-push validation.
# =============================================================================

.PHONY: help
help: ## Show available targets
	@echo "============================================================================="
	@echo "Root Makefile - CI/CD Orchestration"
	@echo "============================================================================="
	@echo ""
	@echo "📋 Prerequisites:"
	@echo "  • make"
	@echo "  • npm + npx (Node.js package management)"
	@echo "  • uv (Python project management - for backend/docs)"
	@echo "  • docker (for database and containerized services)"
	@echo "  • helm (for Kubernetes deployments - optional)"
	@echo ""
	@echo "📦 Setup:"
	@echo "  make install          Install all dependencies and git hooks"
	@echo "  make clean            Clean all build artifacts"
	@echo ""
	@echo "🔍 CI Validation (use before pushing to dev/stage/main):"
	@echo "  make ci               Run all CI checks (lint + type-check + test + build)"
	@echo "  make lint             Run all linters"
	@echo "  make type-check       Run type checking"
	@echo "  make test             Run all tests"
	@echo "  make build            Build all projects"
	@echo ""
	@echo "✨ Code Formatting:"
	@echo "  make format           Format all code"
	@echo ""
	@echo "📚 Documentation:"
	@echo "  make build-docs       Build documentation"
	@echo "  make serve-docs       Serve documentation with live reload"
	@echo ""
	@echo "💡 Development:"
	@echo "  Run dev servers from subfolders:"
	@echo "    cd backend && make dev    (starts backend on :8000)"
	@echo "    cd frontend && make dev   (starts frontend on :9000)"
	@echo ""
	@echo "============================================================================="



# =============================================================================
# Setup & Installation
# =============================================================================

.PHONY: install
install: ## Install all dependencies and set up git hooks
	@echo "Installing root npm dependencies (lefthook + prettier)..."
	npm install
	@echo "Installing git hooks with lefthook..."
	npx lefthook install
	@echo "Installing backend dependencies..."
	cd backend && $(MAKE) install
	@echo "Installing frontend dependencies..."
	cd frontend && $(MAKE) install
	@echo "Installing docs dependencies..."
	cd docs && $(MAKE) install
	@echo "Install env files if missing..."
	@if [ ! -f .database.env ]; then cp .database.env.example .database.env; fi
	@echo "✅ Setup complete!"

.PHONY: clean
clean: ## Remove all build artifacts and dependencies
	@echo "Cleaning root dependencies..."
	rm -rf node_modules package-lock.json
	@echo "Cleaning backend..."
	cd backend && $(MAKE) clean
	@echo "Cleaning frontend..."
	cd frontend && $(MAKE) clean
	@echo "✅ Clean complete!"

# =============================================================================
# Development - Database Services
# =============================================================================

.PHONY: run-db
run-db:
	docker compose up -d --pull=always postgres

.PHONY: stop-db
stop-db:
	docker compose down
.PHONY: clean-db
clean-db:
	docker compose down -v
	docker volume rm co2-calculator_postgres-data-18 || true

# =============================================================================
# CI/CD - Validation Commands
# =============================================================================

.PHONY: ci
ci: ## Run all CI checks (use before pushing to dev/stage/main)
	@echo "Running CI validation pipeline..."
	@set -e; \
	$(MAKE) lint && \
	$(MAKE) type-check && \
	$(MAKE) test && \
	$(MAKE) build
	@echo "✅ All CI checks passed!"

# =============================================================================
# Code Formatting
# =============================================================================

.PHONY: format
format: ## Format all code (root, backend, frontend, docs, helm)
	@echo "\033[36mFormatting root files...\033[0m"
	@npx prettier --write "*.md" "*.json" "*.yml" --ignore-unknown --ignore-path .prettierignore
	@if [ -d "backend" ]; then $(MAKE) -C backend format FILES="."; fi
	@if [ -d "frontend" ]; then $(MAKE) -C frontend format FILES="."; fi
	@echo "\033[32m✅ Formatting complete!\033[0m"

# =============================================================================
# Linting
# =============================================================================

.PHONY: lint
lint: ## Run all linters (backend, frontend, docs, helm)
	@echo "\033[36mRunning linters...\033[0m"
	@set -e; \
	if [ -d "backend" ]; then \
		echo "\033[33mLinting backend...\033[0m"; \
		$(MAKE) -C backend lint FILES="."; \
	fi; \
	if [ -d "frontend" ]; then \
		echo "\033[33mLinting frontend...\033[0m"; \
		$(MAKE) -C frontend lint FILES="."; \
	fi; \
	if [ -d "docs" ]; then \
		echo "\033[33mLinting docs...\033[0m"; \
		$(MAKE) -C docs lint FILES="."; \
	fi; \
	if [ -d "helm" ]; then \
		echo "\033[33mLinting helm...\033[0m"; \
		$(MAKE) -C helm lint FILES="."; \
	fi
	@echo "\033[32m✅ Linting complete!\033[0m"

# =============================================================================
# Type Checking
# =============================================================================

.PHONY: type-check
type-check: ## Run type checking (backend + frontend)
	@echo "\033[36mRunning type checks...\033[0m"
	@set -e; \
	if [ -d "backend" ]; then $(MAKE) -C backend type-check FILES="."; fi; \
	if [ -d "frontend" ]; then $(MAKE) -C frontend type-check FILES="."; fi
	@echo "\033[32m✅ Type checking complete!\033[0m"

# =============================================================================
# Testing
# =============================================================================

.PHONY: test
test: ## Run all tests (backend + frontend)
	@echo "\033[36mRunning tests...\033[0m"
	@set -e; \
	if [ -d "backend" ]; then $(MAKE) -C backend test; fi; \
	if [ -d "frontend" ]; then $(MAKE) -C frontend test; fi
	@echo "\033[32m✅ All tests passed!\033[0m"

# =============================================================================
# Building
# =============================================================================

.PHONY: build
build: ## Build all projects (backend + frontend)
	@echo "\033[36mBuilding projects...\033[0m"
	@set -e; \
	if [ -d "backend" ]; then $(MAKE) -C backend build; fi; \
	if [ -d "frontend" ]; then $(MAKE) -C frontend build; fi
	@echo "\033[32m✅ Build complete!\033[0m"

# =============================================================================
# Documentation
# =============================================================================

.PHONY: build-docs
build-docs: ## Build documentation site
	@echo "Building documentation..."
	if [ -d "docs" ]; then cd docs && $(MAKE) build-docs; fi
	@echo "✅ Documentation built!"

.PHONY: serve-docs
serve-docs: ## Serve documentation with live reload
	@echo "Starting documentation server..."
	if [ -d "docs" ]; then cd docs && $(MAKE) serve-docs; fi


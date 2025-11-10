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
	@echo "Formatting root files..."
	@npx prettier --write "*.md" "*.json" "*.yml" --ignore-unknown --ignore-path .prettierignore
	@if [ -d "backend" ]; then cd backend && $(MAKE) format FILES="."; fi
	@if [ -d "frontend" ]; then cd frontend && $(MAKE) format FILES="."; fi
# 	@if [ -d "docs" ]; then cd docs && $(MAKE) format FILES="."; fi
# 	@if [ -d "helm" ]; then cd helm && $(MAKE) format FILES="."; fi
	@echo "✅ Formatting complete!"

# =============================================================================
# Linting
# =============================================================================

.PHONY: lint
lint: ## Run all linters (backend, frontend, docs, helm)
	@echo "Running linters..."
	@set -e; \
	if [ -d "backend" ]; then cd backend && $(MAKE) lint FILES="."; fi; \
	if [ -d "frontend" ]; then cd frontend && $(MAKE) lint FILES="."; fi; \
	if [ -d "docs" ]; then cd docs && $(MAKE) lint FILES="."; fi; \
	if [ -d "helm" ]; then cd helm && $(MAKE) lint FILES="."; fi
	@echo "✅ Linting complete!"

# =============================================================================
# Type Checking
# =============================================================================

.PHONY: type-check
type-check: ## Run type checking (backend + frontend)
	@echo "Running type checks..."
	@set -e; \
	if [ -d "backend" ]; then cd backend && $(MAKE) type-check FILES="."; fi; \
	if [ -d "frontend" ]; then cd frontend && $(MAKE) type-check FILES="."; fi
	@echo "✅ Type checking complete!"

# =============================================================================
# Testing
# =============================================================================

.PHONY: test
test: ## Run all tests (backend + frontend)
	@echo "Running tests..."
	@set -e; \
	if [ -d "backend" ]; then cd backend && $(MAKE) test; fi; \
	if [ -d "frontend" ]; then cd frontend && $(MAKE) test; fi
	@echo "✅ All tests passed!"

# =============================================================================
# Building
# =============================================================================

.PHONY: build
build: ## Build all projects (backend + frontend)
	@echo "Building projects..."
	@set -e; \
	if [ -d "backend" ]; then cd backend && $(MAKE) build; fi; \
	if [ -d "frontend" ]; then cd frontend && $(MAKE) build; fi
	@echo "✅ Build complete!"

# =============================================================================
# Documentation
# =============================================================================

.PHONY: build-docs
build-docs: ## Build documentation site
	@echo "Building documentation..."
	UV_NO_ISOLATION=1 uv run mkdocs build
	@echo "✅ Documentation built!"

.PHONY: serve-docs
serve-docs: ## Serve documentation with live reload
	@echo "Starting documentation server..."
	mkdocs serve --dirtyreload --watch docs --watch mkdocs.yml


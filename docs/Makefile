# FILES can be overridden to target specific files (for git hooks)
FILES ?= .

.PHONY: help
help: ## Show this help message
	@echo "Frontend Makefile targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'


.PHONY: format
format: ## Format Markdown files
	@echo "Formatting documentation..."
	@npx prettier --write $(FILES) --ignore-unknown

.PHONY: lint
lint: ## Check Markdown formatting without fixing
	@echo "Checking documentation formatting..."
	@npx prettier --check $(FILES) --ignore-unknown

.PHONY: install
install: ## Install documentation dependencies
	@echo "Installing documentation dependencies..."
	UV_NO_ISOLATION=1 uv sync --locked --all-extras --dev
	@echo "Documentation dependencies installed!"


.PHONY: docker-build-run
docker-build-run: ## Build and run documentation in Docker (convenience target)
	docker build -t docs:test . && docker run --rm -p 8080:8080 docs:test

# Zensical has no plugin API: the section and plan indexes are written to
# disk first. --strict fails on dead page links and anchors, check_links.py
# on dead image and repository-file links.
.PHONY: build-docs
build-docs: ## Build documentation, failing on any dead link
	UV_NO_ISOLATION=1 uv run python gen_indexes.py
	UV_NO_ISOLATION=1 uv run zensical build --clean --strict
	UV_NO_ISOLATION=1 uv run python check_links.py site

.PHONY: serve-docs
serve-docs: ## Serve documentation with live reload (rerun to refresh the plan index)
	UV_NO_ISOLATION=1 uv run python gen_indexes.py
	UV_NO_ISOLATION=1 uv run zensical serve

# Exploratory Vite + Eta build (#3002), opt-in: build-docs above is what
# CI and the image use. Node only; see eta/ and plan 3002-vite-eta-docs.
.PHONY: install-docs-eta
install-docs-eta: ## Install the Vite + Eta build's dependencies
	npm --prefix eta ci

.PHONY: build-docs-eta
build-docs-eta: ## Build the docs with Vite + Eta into eta/dist, failing on any dead link
	npm --prefix eta run build
	UV_NO_ISOLATION=1 uv run python check_links.py eta/dist

.PHONY: serve-docs-eta
serve-docs-eta: ## Serve the Vite + Eta docs with live reload on http://localhost:8002
	npm --prefix eta run dev

.PHONY: docker-build-run-eta
docker-build-run-eta: ## Build and run the Vite + Eta docs image on http://localhost:8080
	docker build -f eta/Dockerfile -t docs:eta . && docker run --rm -p 8080:8080 docs:eta

.PHONY: clean
clean: ## Clean built documentation
	rm -rf site/ eta/dist/ eta/.tmp/

.PHONY: clean-docker
clean-docker: ## Remove Docker images
	docker rmi -f co2-docs docs:test docs:eta 2>/dev/null || true

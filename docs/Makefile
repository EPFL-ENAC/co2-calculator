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

.PHONY: build-docs
build-docs: ## Build documentation into site/, failing on any warning or dead link
	sh build.sh

.PHONY: serve-docs
serve-docs: ## Serve documentation with live reload on http://127.0.0.1:8001
	uv run python gen_indexes.py
	uv run zensical serve

.PHONY: clean
clean: ## Clean built documentation
	rm -rf site/

.PHONY: clean-docker
clean-docker: ## Remove Docker images
	docker rmi -f co2-docs docs:test 2>/dev/null || true

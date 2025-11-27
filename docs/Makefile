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
	

.PHONY: pdf
pdf: ## Build documentation with PDF export enabled
	cd docs && $(MAKE) pdf
	UV_NO_ISOLATION=1 ENABLE_PDF_EXPORT=1 uv run mkdocs build

.PHONY: build-docs
build-docs: ## Build documentation
	UV_NO_ISOLATION=1 uv run mkdocs build

.PHONY: serve-docs
serve-docs: ## Serve documentation with live reload
	UV_NO_ISOLATION=1 uv run mkdocs serve --dirtyreload --watch src --watch mkdocs.yml

.PHONY: clean-docs
clean-docs: ## Clean built documentation
	rm -rf site/
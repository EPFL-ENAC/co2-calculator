.PHONY: format format-check lint

# FILES can be overridden to target specific files (for git hooks)
FILES ?= .

format: ## Format Markdown files
	@echo "Formatting documentation..."
	@npx prettier --write $(FILES) --ignore-unknown

format-check: ## Check Markdown formatting without fixing
	@echo "Checking documentation formatting..."
	@npx prettier --check $(FILES) --ignore-unknown

lint: format-check ## Lint documentation (alias for format-check)

install: ## Install documentation dependencies
	

pdf: ## Build documentation with PDF export enabled
	cd docs && $(MAKE) pdf
	UV_NO_ISOLATION=1 ENABLE_PDF_EXPORT=1 uv run mkdocs build

build-docs: ## Build documentation
	UV_NO_ISOLATION=1 uv run mkdocs build

serve-docs: ## Serve documentation with live reload
	mkdocs serve --dirtyreload --watch docs --watch mkdocs.yml

clean-docs: ## Clean built documentation
	rm -rf site/
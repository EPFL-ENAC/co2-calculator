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

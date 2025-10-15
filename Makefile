.PHONY: install clean uninstall help

# Default target
.PHONY: help
help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'



install: ## Install npm dependencies and set up git hooks
	@echo "Installing npm dependencies..."
	npm install
	@echo "Syncing uv environment..."
	uv sync
	@echo "Installing git hooks with lefthook..."
	npx lefthook install
	@echo "Setup complete!"

pdf: ## Build documentation with PDF export enabled
	UV_NO_ISOLATION=1 ENABLE_PDF_EXPORT=1 uv run mkdocs build
build-docs: ## Build documentation
	UV_NO_ISOLATION=1 uv run mkdocs build


serve: ## Serve documentation with live reload
	UV_NO_ISOLATION=1 WATCHDOG_OBSERVER=polling mkdocs serve --dirtyreload --watch docs --watch mkdocs.yml

clean: ## Remove node_modules and package-lock.json
	@echo "Cleaning dependencies..."
	rm -rf node_modules
	rm -f package-lock.json

# Uninstall hooks and clean
uninstall: ## Uninstall git hooks and clean dependencies
	@echo "Uninstalling git hooks..."
	npx lefthook uninstall || true
	$(MAKE) clean
	@echo "Uninstall complete!"


lint: ## Run linters on the codebase
	@echo "Running linter..."
	LEFTHOOK=0 npx lefthook run pre-commit
	@echo "Linting complete!"

format: ## Format codebase
	@echo "Running formatter..."
	@echo "Formatting Markdown files..."
	npx prettier --write . --ignore-unknown --ignore-path .prettierignore
	@echo "Formatting JavaScript/TypeScript files..."
	if [ -d "frontend" ]; then \
		npx prettier --write frontend --ignore-unknown --ignore-path .prettierignore && npx eslint frontend --ext .js,.ts,.jsx,.tsx --fix; \
	else \
		echo "No frontend directory found, skipping JavaScript/TypeScript formatting"; \
	fi
	@echo "Formatting CSS/SCSS files..."
	if [ -d "frontend" ]; then \
		npx stylelint "frontend/**/*.{css,scss}" --fix 2>/dev/null || echo "No CSS/SCSS files found or stylelint error"; \
	else \
		echo "No frontend directory found, skipping CSS/SCSS formatting"; \
	fi
	@echo "Formatting Python files..."
	if [ -d "backend" ]; then \
		if command -v uv >/dev/null 2>&1; then \
			uv run ruff format backend 2>/dev/null || echo "No Python files found or ruff error"; \
		else \
			echo "uv not found, skipping Python formatting"; \
		fi \
	else \
		echo "No backend directory found, skipping Python formatting"; \
	fi
	@echo "Formatting complete!"

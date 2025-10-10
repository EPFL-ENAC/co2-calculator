.PHONY: install clean uninstall help

# Default target
help:
	@echo "Available commands:"
	@echo "  install    - Install dependencies and set up git hooks"
	@echo "  clean      - Clean node_modules and package-lock.json"
	@echo "  uninstall  - Remove git hooks and clean dependencies"
	@echo "  help       - Show this help message"


# Install dependencies and set up git hooks
install:
	@echo "Installing npm dependencies..."
	npm install
	@echo "Installing git hooks with lefthook..."
	npx lefthook install
	@echo "Setup complete!"

# Clean dependencies
clean:
	@echo "Cleaning dependencies..."
	rm -rf node_modules
	rm -f package-lock.json

# Uninstall hooks and clean
uninstall:
	@echo "Uninstalling git hooks..."
	npx lefthook uninstall || true
	$(MAKE) clean
	@echo "Uninstall complete!"


lint:
	@echo "Running linter..."
	LEFTHOOK=0 npx lefthook run pre-commit
	@echo "Linting complete!"

format:
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

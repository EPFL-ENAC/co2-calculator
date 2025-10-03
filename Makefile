.PHONY: setup install clean uninstall help

# Default target
help:
	@echo "Available commands:"
	@echo "  setup      - Set up repository from template (first-time setup)"
	@echo "  install    - Install dependencies and set up git hooks"
	@echo "  clean      - Clean node_modules and package-lock.json"
	@echo "  uninstall  - Remove git hooks and clean dependencies"
	@echo "  help       - Show this help message"

# SETUP SECTION START
# Setup repository from template
setup:
	@echo "Setting up repository from template..."
	./setup-repo.sh

# SETUP SECTION END

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
	npx prettier --check .
	@echo "Linting complete!"

format:
	@echo "Running formatter..."
	npx prettier --write .
	@echo "Formatting complete!"
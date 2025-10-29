.PHONY: help install clean run
.PHONY: dev build test test-watch format format-check lint

help: ## Show this help message
	@echo "Frontend Makefile targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install frontend dependencies
	@echo "Installing frontend dependencies..."
	npm install
	@echo "Frontend dependencies installed!"

clean: ## Clean frontend dependencies
	@echo "Cleaning frontend dependencies..."
	rm -rf node_modules dist
	rm -f package-lock.json
	@echo "Frontend cleaned!"

# Capture all arguments after the target (lazy evaluation)
ARGS = $(filter-out $@,$(MAKECMDGOALS))

run: ## Run npm script or list available scripts (usage: make run <script> [args])
	@if [ -n "$(ARGS)" ]; then \
		npm run $(firstword $(ARGS)) -- $(wordlist 2,$(words $(ARGS)),$(ARGS)); \
	else \
		echo "No script specified — listing npm scripts:"; \
		npm run; \
	fi

# Allow passing arguments to make targets
%:
	@:
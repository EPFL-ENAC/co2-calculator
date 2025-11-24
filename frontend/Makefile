.PHONY: help
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Install dependencies
	npm install

.PHONY: clean
clean: ## Clean up generated files
	rm -rf node_modules dist
	rm -f package-lock.json

# FILES can be overridden to target specific files (for git hooks)
FILES ?= .

# File filters
JS_FILES       := $(filter %.js %.ts %.jsx %.tsx %.vue,$(FILES))
CSS_FILES      := $(filter %.css %.scss,$(FILES))
PRETTIER_FILES := $(filter-out %.js %.ts %.jsx %.tsx %.vue %.css %.scss,$(FILES))

# =============================================================================
# Development Tasks
# =============================================================================

.PHONY: format
format: ## Format code with prettier, eslint, and stylelint
	@set -e; \
	if [ "$(FILES)" = "." ]; then \
		npx prettier --write . --ignore-unknown && \
		npx eslint --fix . --ext .js,.ts,.jsx,.tsx,.vue && \
		npx stylelint --fix "**/*.{css,scss}"; \
	else \
		if [ -n "$(PRETTIER_FILES)" ]; then \
			npx prettier --write $(PRETTIER_FILES) --ignore-unknown; \
		fi; \
		if [ -n "$(JS_FILES)" ]; then \
			npx eslint --fix $(JS_FILES); \
		fi; \
		if [ -n "$(CSS_FILES)" ]; then \
			npx stylelint --fix $(CSS_FILES); \
		fi; \
	fi

.PHONY: lint
lint: ## Check code formatting
	@set -e; \
	if [ "$(FILES)" = "." ]; then \
		npx prettier --check . --ignore-unknown && \
		npx eslint . && \
		npx stylelint "**/*.{css,scss}"; \
	else \
		if [ -n "$(PRETTIER_FILES)" ]; then \
			npx prettier --check $(PRETTIER_FILES) --ignore-unknown; \
		fi; \
		if [ -n "$(JS_FILES)" ]; then \
			npx eslint $(JS_FILES); \
		fi; \
		if [ -n "$(CSS_FILES)" ]; then \
			npx stylelint $(CSS_FILES); \
		fi; \
	fi

.PHONY: type-check
type-check: ## Run TypeScript type checking
	@set -e; \
	npx tsc --noEmit && \
	npx vue-tsc --noEmit

.PHONY: test
test: ## Run tests (component + e2e)
	@set -e; \
	npm run test-ct && \
	npm run test:e2e

.PHONY: dev
dev: ## Start development server
	npm run dev

.PHONY: build
build: ## Build Docker image
	docker build -t co2-calculator-frontend .
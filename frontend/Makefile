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

TSGO := $(shell which tsgo)


# https://github.com/KazariEX/vue-tsgo
.PHONY: type-check-go
type-check-go: ## Run TypeScript type checking
	@if [ -z "$(TSGO)" ]; then echo "Error: tsgo not found in PATH"; exit 1; fi
	@$(TSGO) --noEmit -p tsconfig.typecheck.json

.PHONY: type-check
type-check: ## Run TypeScript type checking
	@set -e; \
	npx vue-tsc --noEmit -p tsconfig.typecheck.json


.PHONY: type-check-full
type-check-full:  ## Run TypeScript type checking
	@set -e; \
	$(MAKE) type-check-go & \
	$(MAKE) type-check & \
	wait


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

# =============================================================================
# Storybook Tasks
# =============================================================================

.PHONY: storybook
storybook: ## Start Storybook development server
	npm run storybook

.PHONY: storybook-build
storybook-build: ## Build static Storybook site
	npm run storybook:build

.PHONY: storybook-test
storybook-test: ## Test Storybook stories
	npm run storybook:test

.PHONY: storybook-test-ci
storybook-test-ci: ## Test Storybook stories in CI mode
	npm run storybook:test-ci

.PHONY: storybook-docker
storybook-docker: ## Build and run Storybook in Docker
	docker build -f Dockerfile.storybook -t storybook .
	docker run -p 8080:8080 storybook
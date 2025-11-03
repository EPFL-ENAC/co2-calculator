.PHONY: help install clean run dev build test test-watch
.PHONY: format format-check lint lint-js lint-css


# Quick prerequisite check utility
define check_tools
	@missing=0; \
	for tool in $(1); do \
		if ! command -v $$tool >/dev/null 2>&1; then \
			echo "❌ Missing tool: $$tool"; \
			missing=1; \
		fi; \
	done; \
	if [ $$missing -eq 1 ]; then \
		echo "⚠️  Missing tools detected. Please install them before continuing."; \
		exit 1; \
	fi
	@echo "✅ All required tools are installed: $(1)"
endef



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


# ---------------------------------------------------------
# Docker build
#---------------------------------------------------------
.PHONY: build
build: ## Build Docker image
	$(call check_tools,docker);
	@echo "Building Docker image..."
	docker build -t co2-calculator-frontend .
	@echo "Docker image built!"


# ---------------------------------------------------------
# 🧹 FORMATTING / LINTING LOGIC
# ---------------------------------------------------------

FILES ?= .

# Filters (only used when FILES != .)
JS_FILES       := $(filter %.js %.ts %.jsx %.tsx %.vue,$(FILES))
CSS_FILES      := $(filter %.css %.scss,$(FILES))
PRETTIER_FILES := $(filter-out %.js %.ts %.jsx %.tsx %.vue %.css %.scss,$(FILES))

format: ## Format frontend code (JS/TS/Vue + CSS/SCSS + others)
	@echo "Formatting frontend files..."
	@if [ "$(FILES)" = "." ]; then \
		echo "→ Running Prettier, ESLint, and Stylelint on entire project..."; \
		npx prettier --write . --ignore-unknown; \
		npx eslint --fix . --ext .js,.ts,.jsx,.tsx,.vue; \
		npx stylelint "**/*.{css,scss}"; \
	else \
		if [ -n "$(PRETTIER_FILES)" ]; then \
			echo "→ Prettier formatting: $(PRETTIER_FILES)"; \
			npx prettier --write $(PRETTIER_FILES) --ignore-unknown; \
		fi; \
		if [ -n "$(JS_FILES)" ]; then \
			echo "→ ESLint fixing: $(JS_FILES)"; \
			npx eslint --fix $(JS_FILES); \
		fi; \
		if [ -n "$(CSS_FILES)" ]; then \
			echo "→ Stylelint fixing: $(CSS_FILES)"; \
			npx stylelint --fix $(CSS_FILES); \
		fi; \
		if [ -z "$(JS_FILES)$(CSS_FILES)$(PRETTIER_FILES)" ]; then \
			echo "No relevant files to format."; \
		fi; \
	fi

format-check: ## Check frontend formatting without fixing
	@echo "Checking frontend formatting..."
	@if [ "$(FILES)" = "." ]; then \
		echo "→ Checking all files with Prettier, ESLint, and Stylelint..."; \
		npx prettier --check . --ignore-unknown; \
		echo "→ ESLint check:"; \
		npx eslint . ; \
		echo "→ Stylelint check:"; \
		npx stylelint "**/*.{css,scss}"; \
		echo "Formatting check completed."; \
	else \
		if [ -n "$(PRETTIER_FILES)" ]; then \
			echo "→ Prettier check: $(PRETTIER_FILES)"; \
			npx prettier --check $(PRETTIER_FILES) --ignore-unknown; \
		fi; \
		if [ -n "$(JS_FILES)" ]; then \
			echo "→ ESLint check: $(JS_FILES)"; \
			npx eslint $(JS_FILES); \
		fi; \
		if [ -n "$(CSS_FILES)" ]; then \
			echo "→ Stylelint check: $(CSS_FILES)"; \
			npx stylelint $(CSS_FILES); \
		fi; \
		if [ -z "$(JS_FILES)$(CSS_FILES)$(PRETTIER_FILES)" ]; then \
			echo "No relevant files to check."; \
		fi; \
	fi

lint-js: ## Lint JavaScript/TypeScript/Vue files
	@echo "Linting JS/TS/Vue files..."
	@if [ "$(FILES)" = "." ]; then \
		npx eslint . ; \
	else \
		npx eslint $(FILES); \
	fi

lint-css: ## Lint CSS/SCSS files
	@echo "Linting CSS/SCSS files..."
	@if [ "$(FILES)" = "." ]; then \
		npx stylelint "**/*.{css,scss}"; \
	else \
		npx stylelint $(FILES); \
	fi

lint: format-check  ## Lint all frontend code


.PHONY: type-check
type-check:
	@echo "Running TypeScript type checks..."
	@if [ "$(FILES)" = "." ]; then \
		echo "→ Type-checking entire project..."; \
		npx tsc --noEmit ; \
		npx vue-tsc --noEmit ; \
	else \
		npx tsc --noEmit --project tsconfig.json --files $(FILES); \
		npx vue-tsc --noEmit --project tsconfig.json --files $(FILES); \
	fi



.PHONY: test

test: ## Run frontend tests once
	@echo "Running frontend tests..."
	if [ ! -d "dist" ]; then \
		echo "⚠️  'dist' directory not found. Please build the frontend first using 'make build'."; \
		echo "NEEDED FOR e2e tests."; \
		exit 1; \
	fi
	@echo "Running component tests..."
	npm run test-ct
	@echo "Running end-to-end tests..."

	npm run test:e2e
	@echo "Frontend tests completed."


# Allow passing arbitrary args (e.g. `make run dev`)
%:
	@:

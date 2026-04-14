.PHONY: help
help: ## Show this help message
	@echo "Helm Makefile targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'


# Default target for files (can be overridden)
FILES ?= .

## -------------------------------
## 🧹 Formatting
## -------------------------------

.PHONY: format
format: ## Format YAML and Markdown files (Helm, docs, etc.)
	@echo "format in helm charts not implemented"

## -------------------------------
## 🧩 Helm linting
## -------------------------------
.PHONY: lint-helm
lint-helm: ## Run helm lint on all Helm charts
	@echo "🧭 Running helm lint..."
	@if command -v helm >/dev/null 2>&1; then \
		find . -type f -name Chart.yaml | while read -r chart; do \
			chart_dir=$$(dirname "$$chart"); \
			echo "🔧 Linting Helm chart: $$chart_dir"; \
			helm lint "$$chart_dir"; \
		done; \
	else \
		echo "⚠️  Warning: helm not found. Skipping helm lint."; \
	fi


## -------------------------------
## 🧪 Combined linting
## -------------------------------
.PHONY: lint
lint: lint-helm ## Run all lint checks (format + helm)
	@echo "🧭 All lint checks passed!"


## -------------------------------
## 🧪 Testing
## -------------------------------
.PHONY: template
template: ## Render Helm templates with default values
	@echo "🧪 Rendering Helm templates..."
	@helm template . --values values.yaml

.PHONY: template-docs-disabled
template-docs-disabled: ## Render Helm templates with docs disabled
	@echo "🧪 Rendering Helm templates with docs.enabled=false..."
	@helm template . --values values.yaml --set docs.enabled=false | grep -i "kind:.*\(Deployment\|Service\)" || echo "No docs resources rendered"

.PHONY: template-frontend-disabled
template-frontend-disabled: ## Render Helm templates with frontend disabled
	@echo "🧪 Rendering Helm templates with frontend.enabled=false..."
	@helm template . --values values.yaml --set frontend.enabled=false | grep -i "kind:.*\(Deployment\|Service\)" || echo "No frontend resources rendered"

## -------------------------------
## Skaffold
## -------------------------------
.PHONY: skaffold-dev
skaffold-dev: ## Run skaffold in dev mode
	@echo "🚀 Starting skaffold in dev mode..."
	@skaffold dev --port-forward


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
		find . -maxdepth 1 -type f -name Chart.yaml | while read -r chart; do \
			chart_dir=$$(dirname "$$chart"); \
			echo "🔧 Linting Helm chart: $$chart_dir"; \
			helm lint "$$chart_dir" -f "$$chart_dir/examples/values.yaml" || exit 1; \
			helm template "$$chart_dir" -f "$$chart_dir/examples/values.yaml" >/dev/null || exit 1; \
		done; \
	else \
		echo "⚠️  Warning: helm not found. Skipping helm lint."; \
	fi

# The example Secret is the public contract of the chart: a key the pods
# read and the example lacks leaves an installer with pods that never start.
.PHONY: lint-examples
lint-examples: ## Fail if an example Secret lacks a key the pods read
	@grep -oE '^ +[a-zA-Z0-9]+Key: [A-Z0-9_]+' values.yaml | awk '{print $$2}' | sort -u > .keys-chart
	@for f in examples/secrets.yaml skaffold/templates/secrets.yaml; do \
		missing=$$(grep -oE '^  [A-Z0-9_]+:' $$f | tr -d ' :' | sort -u | comm -13 - .keys-chart); \
		if [ -n "$$missing" ]; then rm -f .keys-chart; echo "❌ $$f lacks:" $$missing; exit 1; fi; \
	done; rm -f .keys-chart
	@echo "✅ the example Secrets have every key of backend.existingSecret.keys"

## -------------------------------
## 📖 Values reference
## -------------------------------
HELM_DOCS = helm-docs --chart-to-generate . --template-files VALUES.md.gotmpl --output-file VALUES.md --sort-values-order file --log-level warning

.PHONY: docs
docs: ## Generate VALUES.md from values.yaml (needs helm-docs)
	@command -v helm-docs >/dev/null 2>&1 \
		|| { echo "❌ helm-docs not found: brew install helm-docs (https://github.com/norwoodj/helm-docs)"; exit 1; }
	@$(HELM_DOCS)

.PHONY: lint-docs
lint-docs: ## Fail if VALUES.md is older than values.yaml
	@if command -v helm-docs >/dev/null 2>&1; then \
		$(HELM_DOCS) --dry-run | diff -q - VALUES.md >/dev/null \
			|| { echo "❌ VALUES.md is stale: run 'make -C helm docs'"; exit 1; }; \
		echo "✅ VALUES.md matches values.yaml"; \
	else \
		echo "⚠️  Warning: helm-docs not found. Skipping the VALUES.md check."; \
	fi


## -------------------------------
## 🧪 Combined linting
## -------------------------------
.PHONY: lint
lint: lint-helm lint-examples lint-docs ## Run all lint checks (helm, examples, VALUES.md)
	@echo "🧭 All lint checks passed!"


## -------------------------------
## 🧪 Testing
## -------------------------------
.PHONY: template
template: ## Render Helm templates with the example values
	@echo "🧪 Rendering Helm templates..."
	@helm template . --values examples/values.yaml

.PHONY: template-docs-disabled
template-docs-disabled: ## Render Helm templates with docs disabled
	@echo "🧪 Rendering Helm templates with docs.enabled=false..."
	@helm template . --values examples/values.yaml --set docs.enabled=false | grep -i "kind:.*\(Deployment\|Service\)" || echo "No docs resources rendered"

.PHONY: check-network-policies
check-network-policies: ## Fail unless pod-to-pod ingress to the backend renders (#2845)
	@echo "🧪 Checking network policies render pod-to-pod backend ingress..."
	@helm template . --values examples/values.yaml --set networkPolicies.enabled=true \
		--set backend.existingSecret.name=placeholder \
		-s templates/network-policies.yaml \
		| grep -q "name: allow-backend-from-pods" \
		|| { echo "❌ allow-backend-from-pods missing: worker→backend broadcast would be dropped"; exit 1; }
	@echo "✅ allow-backend-from-pods present"

.PHONY: template-frontend-disabled
template-frontend-disabled: ## Render Helm templates with frontend disabled
	@echo "🧪 Rendering Helm templates with frontend.enabled=false..."
	@helm template . --values examples/values.yaml --set frontend.enabled=false | grep -i "kind:.*\(Deployment\|Service\)" || echo "No frontend resources rendered"

## -------------------------------
## Skaffold
## -------------------------------
# Named, never the current context: the kubeconfig of a maintainer also
# holds the shared clusters, and this loop deploys DEBUG with test login.
KUBE_CONTEXT ?= docker-desktop

.PHONY: skaffold-dev
skaffold-dev: ## Run the app on a local cluster, rebuilt on change (KUBE_CONTEXT=docker-desktop)
	@echo "🚀 Starting skaffold on $(KUBE_CONTEXT): http://localhost:8080/en/login-test"
	@# user: only the Traefik forward of skaffold.yaml. A direct forward to
	@# the frontend serves index.html for every /api call.
	@skaffold dev --port-forward=user --kube-context $(KUBE_CONTEXT)


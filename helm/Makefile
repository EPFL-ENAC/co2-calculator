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
			helm template "$$chart_dir" -f "$$chart_dir/skaffold/values-app.yaml" >/dev/null || exit 1; \
		done; \
	else \
		echo "⚠️  Warning: helm not found. Skipping helm lint."; \
		[ -z "$$CI" ] || { echo "❌ helm is required in CI"; exit 1; }; \
	fi

# The example Secret is the public contract of the chart: a key the pods
# read and the example lacks leaves an installer with pods that never start.
# The keys come from the render, so a template change cannot hide one.
.PHONY: lint-examples
lint-examples: ## Fail if an example Secret lacks a key the pods read
	@keys=$$(helm template . -f examples/values.yaml \
		| awk '/secretKeyRef:/{ref=1; next} ref && /key:/{print $$2; ref=0} /^ *- key:/{print $$3}' | sort -u); \
	[ -n "$$keys" ] || { echo "❌ no Secret key found in the render"; exit 1; }; \
	for f in examples/secrets.yaml skaffold/templates/secrets.yaml; do \
		missing=""; \
		for k in $$keys; do grep -q "^  $$k:" $$f || missing="$$missing $$k"; done; \
		[ -z "$$missing" ] || { echo "❌ $$f lacks:$$missing"; exit 1; }; \
	done; \
	echo "✅ the example Secrets have the $$(echo "$$keys" | wc -l | tr -d ' ') keys the pods read"
	@# A committed signing or encryption value would boot any copy of the
	@# backend, so Helm must generate each one (randAlphaNum) at install.
	@literal=$$(awk '/_(HMAC_KEY|ENCRYPTION_KEY|ENCRYPTION_SALT):/ && !/randAlphaNum/ {print $$1}' skaffold/templates/secrets.yaml); \
	[ -z "$$literal" ] || { echo "❌ skaffold/templates/secrets.yaml has literal values:" $$literal; exit 1; }; \
	echo "✅ Helm generates the Skaffold signing and encryption values"

# What the chart refuses to render without: the backend Secret name and the
# institution volume (#3244). For the checks that render the chart defaults.
REQUIRED = --set backend.existingSecret.name=x --set frontend.institutionAssets.volume.configMap.name=x

# Regression check: "/api/v1" made every API call 404, because FastAPI
# strips the API_DOCS_PREFIX root path before it routes.
.PHONY: check-api-version
check-api-version: ## Fail unless the backend renders API_VERSION=/v1
	@# Chart defaults, not examples/values.yaml: the example sets API_VERSION
	@# itself for the older published chart, and would hide a reverted default.
	@helm template . $(REQUIRED) -s templates/backend-deployment.yaml \
		| grep -A1 'name: API_VERSION' | grep -q 'value: "/v1"' \
		|| { echo "❌ API_VERSION is not /v1: every /api/v1 call would 404"; exit 1; }
	@echo "✅ API_VERSION renders as /v1"

# Regression check: backend.env had APP_VERSION "0.1.0", which replaced the
# version that the image sets at build time: every cluster reported 0.1.0.
.PHONY: check-app-version
check-app-version: ## Fail if the chart sets APP_VERSION for the backend or the worker
	@out=$$(helm template . $(REQUIRED) --set worker.enabled=true \
		-s templates/backend-deployment.yaml -s templates/backend-worker-deployment.yaml) || exit 1; \
	echo "$$out" | grep -q 'name: APP_VERSION$$' \
		&& { echo "❌ the chart sets APP_VERSION: it replaces the version of the image"; exit 1; }; \
	echo "✅ the backend and the worker keep the APP_VERSION of the image"

# Regression check: the chart gave each empty frontend.env default to the
# pod, and an empty variable wins over values.env of the institution folder:
# the frontend stopped with "APP_INSTITUTION_NAME is required and empty".
.PHONY: check-frontend-env
check-frontend-env: ## Fail if the frontend gets an empty env value, or loses a set one
	@out=$$(helm template . $(REQUIRED) --set frontend.env.APP_CONTACT_EMAIL=a@example.org \
		-s templates/frontend-deployment.yaml) || exit 1; \
	echo "$$out" | grep -q 'value: ""' \
		&& { echo "❌ the frontend gets an empty env value: it erases values.env"; exit 1; }; \
	echo "$$out" | grep -A1 'name: APP_CONTACT_EMAIL$$' | grep -q 'value: "a@example.org"' \
		|| { echo "❌ the frontend lacks a frontend.env value that is set"; exit 1; }
	@echo "✅ the frontend gets only the frontend.env values that are set"

# Regression check: the worker read worker.env only, so every deployment
# copied backend.env into it by hand and the copies drifted.
.PHONY: check-worker-env
check-worker-env: ## Fail unless the worker gets backend.env under worker.env, keeps the reconciler, no duplicate name
	@out=$$(helm template . $(REQUIRED) --set worker.enabled=true \
		--set backend.env.CHECK_ONLY_BACKEND=b --set backend.env.CHECK_SHARED=b \
		--set worker.env.CHECK_SHARED=w --set backend.env.RUN_PIPELINE_RECONCILER=false \
		-s templates/backend-worker-deployment.yaml) || exit 1; \
	echo "$$out" | grep -A1 'name: RUN_PIPELINE_RECONCILER$$' | grep -q 'value: "false"' \
		&& { echo "❌ the worker inherits RUN_PIPELINE_RECONCILER=false: no pod runs the sweep"; exit 1; }; \
	echo "$$out" | grep -A1 'name: CHECK_ONLY_BACKEND$$' | grep -q 'value: "b"' \
		|| { echo "❌ the worker lacks backend.env"; exit 1; }; \
	[ "$$(echo "$$out" | grep -c 'name: CHECK_SHARED$$')" = 1 ] \
		&& echo "$$out" | grep -A1 'name: CHECK_SHARED$$' | grep -q 'value: "w"' \
		|| { echo "❌ CHECK_SHARED must render once, with the worker.env value"; exit 1; }; \
	dups=$$(echo "$$out" | sed -n '/^ *- name: worker$$/,/^ *livenessProbe:/s/^ *- name: \([A-Za-z_][A-Za-z0-9_]*\)$$/\1/p' \
		| sort | uniq -d); \
	[ -z "$$dups" ] || { echo "❌ duplicate worker env names:" $$dups; exit 1; }
	@echo "✅ the worker gets backend.env with worker.env on top"

## -------------------------------
## 📖 Values reference
## -------------------------------
HELM_DOCS = helm-docs --chart-to-generate . --template-files VALUES.md.gotmpl --output-file VALUES.md --sort-values-order file --log-level warning

.PHONY: docs
docs: ## Generate VALUES.md from values.yaml (needs helm-docs)
	@command -v helm-docs >/dev/null 2>&1 \
		|| { echo "❌ helm-docs 1.14.2 not found: brew install helm-docs, or https://github.com/norwoodj/helm-docs/releases/tag/v1.14.2"; exit 1; }
	@$(HELM_DOCS)

.PHONY: lint-docs
lint-docs: ## Fail if VALUES.md is older than values.yaml
	@if command -v helm-docs >/dev/null 2>&1; then \
		$(HELM_DOCS) --dry-run | diff -q - VALUES.md >/dev/null \
			|| { echo "❌ VALUES.md is stale: run 'make -C helm docs'"; exit 1; }; \
		echo "✅ VALUES.md matches values.yaml"; \
	else \
		echo "⚠️  Warning: helm-docs not found. Skipping the VALUES.md check."; \
		[ -z "$$CI" ] || { echo "❌ helm-docs is required in CI"; exit 1; }; \
	fi


# The institution folder comes from an image or from a volume, never both
# and never none: the frontend does not start without theme.conf.
SECRET = --set backend.existingSecret.name=x
INSTITUTION_IMAGE = --set frontend.institutionAssets.image=registry.example.org/co2-institution-univ:1.0.0
INSTITUTION_VOLUME = --set frontend.institutionAssets.volume.configMap.name=x
INSTITUTION_IMAGE_VOLUME = --set frontend.institutionAssets.volume.image.reference=registry.example.org/co2-institution-univ:v1.0.0 --set frontend.institutionAssets.subPath=institution

.PHONY: check-institution-source
check-institution-source: ## Fail unless the institution folder comes from exactly one of image or volume
	@helm template . $(SECRET) $(INSTITUTION_IMAGE) -s templates/frontend-deployment.yaml \
		| grep -A2 "initContainers:" | grep -q "co2-institution-univ:1.0.0" \
		|| { echo "❌ institutionAssets.image renders no init container"; exit 1; }
	@out=$$(helm template . $(SECRET) $(INSTITUTION_VOLUME) -s templates/frontend-deployment.yaml) || exit 1; \
		! echo "$$out" | grep -q "initContainers:" \
		|| { echo "❌ institutionAssets.volume renders an init container"; exit 1; }
	@helm template . $(SECRET) $(INSTITUTION_IMAGE_VOLUME) -s templates/frontend-deployment.yaml \
		| grep -q 'subPath: "institution"' \
		|| { echo "❌ institutionAssets.subPath is not on the mount"; exit 1; }
	@helm template . $(SECRET) $(INSTITUTION_IMAGE) $(INSTITUTION_VOLUME) 2>&1 \
		| grep -q "set image or volume, not both" \
		|| { echo "❌ the chart does not refuse image with volume"; exit 1; }
	@helm template . $(SECRET) 2>&1 | grep -q "needs image or volume" \
		|| { echo "❌ the chart does not refuse a missing institution folder"; exit 1; }
	@echo "✅ the institution folder comes from one of image or volume"

# The client lists (#3196). A proxy missing from one list becomes "the
# client" there, so the two lists must be equal, and each value a CIDR.
ALLOWLIST = $(SECRET) $(INSTITUTION_VOLUME) --set 'clientAllowlist.allowedCidrs={198.51.100.0/24}' --set 'clientAllowlist.trustedProxies={10.20.0.0/16,10.98.42.0/24}'

.PHONY: check-client-allowlist
check-client-allowlist: ## Fail unless the chart refuses client lists that differ or that are not CIDRs
	@helm template . $(ALLOWLIST) --set-string 'backend.env.FORWARDED_ALLOW_IPS=10.20.0.0/16\,10.98.42.0/24' \
		-s templates/client-allowlist-configmap.yaml | grep -q "198.51.100.0/24 0;" \
		|| { echo "❌ equal client lists do not render geo.conf"; exit 1; }
	@helm template . $(ALLOWLIST) --set-string 'backend.env.FORWARDED_ALLOW_IPS=10.20.0.0/16' 2>&1 \
		| grep -q "must equal clientAllowlist.trustedProxies" \
		|| { echo "❌ the chart does not refuse a proxy missing from FORWARDED_ALLOW_IPS"; exit 1; }
	@helm template . $(ALLOWLIST) --set-string 'backend.env.FORWARDED_ALLOW_IPS=10.20.0.0/16\,10.98.42.0/24' \
		--set 'clientAllowlist.allowedCidrs={198.51.100.0/24 0; default 0}' 2>&1 \
		| grep -q "is not a CIDR" \
		|| { echo "❌ the chart does not refuse a value that is not a CIDR"; exit 1; }
	@echo "✅ the client lists are equal and hold only CIDRs"

## -------------------------------
## 🧪 Combined linting
## -------------------------------
.PHONY: lint
lint: lint-helm lint-examples check-api-version check-app-version check-worker-env check-frontend-env check-institution-source check-client-allowlist lint-docs ## Run all lint checks (helm, examples, API_VERSION, worker and frontend env, VALUES.md)
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
# holds the shared clusters, and this loop deploys the test login.
KUBE_CONTEXT ?= docker-desktop

.PHONY: skaffold-dev
skaffold-dev: ## Run the app on a local cluster, rebuilt on change (KUBE_CONTEXT=docker-desktop)
	@echo "🚀 Starting skaffold on $(KUBE_CONTEXT): http://localhost:8090/en/login-test"
	@# user: only the Traefik forward of skaffold.yaml. A direct forward to
	@# the frontend serves index.html for every /api call.
	@skaffold dev --port-forward=user --kube-context $(KUBE_CONTEXT)

.PHONY: skaffold-delete
skaffold-delete: ## Remove the local app and its database (KUBE_CONTEXT=docker-desktop)
	@skaffold delete --kube-context $(KUBE_CONTEXT)

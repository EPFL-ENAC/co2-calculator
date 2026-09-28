# Variables
UV := uv
RUFF ?= $(UV) run ruff
PYTEST ?= $(UV) run pytest


.PHONY: help
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Install dependencies
	@if [ ! -f .env ]; then \
		echo "Creating .env from .env.example..."; \
		cp .env.example .env; \
		echo "⚠️  Update .env with your configuration"; \
	fi
	uv sync --dev

.PHONY: install-prod
install-prod: ## Install production dependencies only
	uv sync

.PHONY: clean
clean: ## Clean up generated files
	rm -rf __pycache__
	rm -rf */__pycache__
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -rf .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# FILES can be overridden to target specific files (for git hooks)
FILES ?= .

# File filters
PY_FILES   := $(filter %.py,$(FILES))
YAML_FILES := $(filter %.yml %.yaml,$(FILES))
MD_FILES   := $(filter %.md,$(FILES))


# =============================================================================
# Development Tasks
# =============================================================================
.PHONY: format
format: ## Format code with ruff and prettier
	@set -e; \
	if [ -n "$(PY_FILES)" ]; then \
		$(RUFF) format $(PY_FILES) && \
		$(RUFF) check --fix $(PY_FILES); \
	else \
		$(RUFF) format . && \
		$(RUFF) check --fix .; \
	fi
	@if [ -n "$(YAML_FILES)" ] || [ -n "$(MD_FILES)" ]; then \
		npx prettier --write $(YAML_FILES) $(MD_FILES) --ignore-unknown; \
	else \
		npx prettier --write . --ignore-unknown; \
	fi

.PHONY: lint
lint: ## Check code formatting
	@set -e; \
	if [ -n "$(PY_FILES)" ]; then \
		$(RUFF) format --check $(PY_FILES) && \
		$(RUFF) check $(PY_FILES); \
	else \
		$(RUFF) format --check . && \
		$(RUFF) check .; \
	fi
	@if [ -n "$(YAML_FILES)" ] || [ -n "$(MD_FILES)" ]; then \
		npx prettier --check $(YAML_FILES) $(MD_FILES) --ignore-unknown; \
	else \
		npx prettier --check . --ignore-unknown; \
	fi

.PHONY: lint-fix
lint-fix: ## Fix code formatting issues
	@set -e; \
	if [ -n "$(PY_FILES)" ]; then \
		$(RUFF) format $(PY_FILES) && \
		$(RUFF) check --fix $(PY_FILES); \
	else \
		$(RUFF) format . && \
		$(RUFF) check --fix .; \
	fi

.PHONY: audit
audit: ## Run security audits with uv-audit and bandit
	@set -e; \
	uvx uv-audit --verbose && \
	uvx bandit -r ./app/ -x tests,.venv

.PHONY: type-check
type-check: ## Run type checking with ty
	@set -e; \
	uv run ty check

.PHONY: test
test: ## Run tests
	@set -e; \
	$(PYTEST) tests/unit -vv --cov=app --cov-report=term-missing --cov-fail-under=60

.PHONY: test-cov
test-cov: ## Run tests with coverage
	@set -e; \
	$(PYTEST) tests/ --cov=app --cov-report=html --cov-report=term-missing  --cov-fail-under=45

.PHONY: test-cov-xml
test-cov-xml: ## Run unit tests with coverage and output XML report (fast, used by PR CI)
	@set -e; \
	$(PYTEST) tests/unit --cov=app --cov-report=xml --cov-report=term-missing --cov-fail-under=60

.PHONY: test-cov-xml-integration
test-cov-xml-integration: ## Run integration tests with coverage and output XML report (slow, used by daily CI)
	@set -e; \
	$(PYTEST) tests/integration --cov=app --cov-report=xml --cov-report=term-missing --cov-fail-under=45

.PHONY: seed-data
seed-data: ## Seed the database with initial data
# seeds fake user + unit associations (for testing)
	# $(UV) run -m app.seed.seed_fake_user_unit
	$(UV) run -m app.seed.seed_locations
	$(UV) run -m app.seed.seed_building_rooms
	$(UV) run -m app.seed.seed_generic_factors

.PHONY: seed-data-random
seed-data-random: ## Seed ~800k random data_entry rows via Faker (issue #222)
	$(UV) run -m app.seed.random_generator.seed_all

.PHONY: seed-units
seed-units: ## Seed units from accred
	$(UV) run -m app.seed.seed_units_from_accred

.PHONY: seed-generic-data
seed-generic-data: ## Seed data entries from seed_data CSVs
	$(UV) run -m app.seed.seed_generic_data_entries

# Years provisioned by `bootstrap-years`; override on the command line.
YEARS ?= 2025 2026

.PHONY: bootstrap-years
bootstrap-years: ## Provision years from INPUT_DATA: config + unit sync + factors + references + reduction objectives, no data entries (usage: make bootstrap-years YEARS="2025 2026")
	$(UV) run -m app.seed.bootstrap_years --years $(YEARS)

.PHONY: exchange-rates
exchange-rates: ## Fetch exchange rates from ECB API and store in database
	$(UV) run exchange-rates

# ---------------------------------------------------------------------------
# Load tests (#2295) — see tests/performance/locustfile.py for the scenarios.
# ---------------------------------------------------------------------------
PERF_HOST ?= http://localhost:8000
PERF_USERS ?= 50
PERF_TIME ?= 3m
PERF_CLASSES ?= ExplorerReadUser
PERF_TAG ?= $(shell echo $(PERF_CLASSES) | tr ' A-Z' '_a-z')_$(PERF_USERS)
PERF_REPORT_DIR ?= tests/performance/reports
# Local docker-compose Postgres; override for another target.
PERF_DB_URL ?= postgresql://co2_user:co2_password@localhost:5432/co2_calculator
PERF_DUMP ?= tests/performance/dumps/perf_backdrop.dump
PERF_USERS_FILE ?= $(PERF_REPORT_DIR)/perf_users.txt
# PERF_UI=1 keeps locust's web UI (http://127.0.0.1:8089) with live charts: the
# run still autostarts with -u/-r/-t, but locust stays up until Ctrl-C, and the
# CSV/HTML report is written when it quits.
PERF_UI ?=
PERF_MODE = $(if $(PERF_UI),--autostart --web-host 127.0.0.1,--headless --only-summary)
PERF_MODE_NOTE = $(if $(PERF_UI),web UI http://127.0.0.1:8089 - Ctrl-C when done,headless - PERF_UI=1 for the web UI)

.PHONY: perf-csvs
perf-csvs: ## Generate per-module ceiling-scale upload CSVs into INPUT_DATA/perf/
	$(UV) run python -m scripts.generate_perf_test_csvs

.PHONY: perf-seed
perf-seed: ## Seed the #2295 load-test backdrop (SEED_NUM_UNITS/SEED_YEARS/SEED_CEILING_SCALE override)
	SEED_NUM_UNITS=$${SEED_NUM_UNITS:-600} \
	SEED_YEARS="$${SEED_YEARS:-2021 2022 2023 2024 2025}" \
	SEED_CEILING_SCALE=$${SEED_CEILING_SCALE:-0.1} \
	SEED_CEILING_UNITS_PREFIX=$${SEED_CEILING_UNITS_PREFIX:-U0} \
	$(UV) run -m app.seed.random_generator.seed_all

.PHONY: perf-load
perf-load: ## One headless locust run: make perf-load PERF_USERS=50 PERF_CLASSES="ExplorerReadUser"
	@mkdir -p $(PERF_REPORT_DIR)
	@test -s $(PERF_USERS_FILE) || test -z "$(PERF_DB_URL)" || psql "$(PERF_DB_URL)" -tAc \
		"select institutional_id || ' ' || case when roles_raw::text like '%principal%' then 'principal' else 'standard' end from users where institutional_id like 'USR%'" \
		> $(PERF_USERS_FILE) 2>/dev/null || true
	@p="$(PERF_HOST)"; p="$${p%%/}"; p="$${p##*:}"; \
	case "$$p" in *[!0-9]*|"") \
		echo "note: $(PERF_HOST) has no numeric port — skipping resource sampling"; \
		rm -f $(PERF_REPORT_DIR)/.sampler.pid;; \
	*) exec $(UV) run python -m tests.performance.resource_sampler --port $$p \
		$(PERF_REPORT_DIR)/$(PERF_TAG)_resources.csv & echo $$! > $(PERF_REPORT_DIR)/.sampler.pid;; \
	esac
	@echo "perf-load: $(PERF_CLASSES) x $(PERF_USERS) users for $(PERF_TIME) against $(PERF_HOST) ($(PERF_MODE_NOTE))"
	@PERF_USERS_FILE="$(PERF_USERS_FILE)" \
	PERF_UNIT_IDS="$${PERF_UNIT_IDS:-$$(test -n "$(PERF_DB_URL)" && psql "$(PERF_DB_URL)" -tAc "select min(id)||'-'||max(id) from units where institutional_code like 'U0%'" 2>/dev/null | tr -d '[:space:]' || true)}" \
	PERF_ROLE="$${PERF_ROLE:-calco2.user.principal}" \
	$(UV) run locust -f tests/performance/locustfile.py $(PERF_CLASSES) \
		--host $(PERF_HOST) $(PERF_MODE) \
		-u $(PERF_USERS) -r $$(( $(PERF_USERS) / 10 + 1 )) -t $(PERF_TIME) \
		--csv $(PERF_REPORT_DIR)/$(PERF_TAG) --html $(PERF_REPORT_DIR)/$(PERF_TAG).html \
		--exit-code-on-error 0; \
	status=$$?; \
	if [ -n "$(PERF_UI)" ] && [ $$status -eq 130 ]; then status=0; fi; \
	if [ -f $(PERF_REPORT_DIR)/.sampler.pid ]; then \
		pid=$$(cat $(PERF_REPORT_DIR)/.sampler.pid); \
		kill -- -$$pid 2>/dev/null || kill $$pid 2>/dev/null; \
		pkill -f "resource_sampler --port" 2>/dev/null; \
		rm -f $(PERF_REPORT_DIR)/.sampler.pid; \
	fi; \
	echo "report: file://$$(pwd)/$(PERF_REPORT_DIR)/$(PERF_TAG).html"; exit $$status

# Dev serves /v1/auth/login-test (DEBUG build), so no cookie copying: each
# VU logs in as the TEST-provider PERF_ROLE. Seeded-user minting is local-only
# (PERF_USERS_FILE off), and write scenarios enqueue real jobs on dev's workers.
PERF_DEV_HOST ?= https://co2-calculator-dev.epfl.ch/api

.PHONY: perf-dev
perf-dev: ## Read-only load against dev, clef en main: make perf-dev [PERF_USERS=50] [PERF_CLASSES=ModuleReadUser]
	@case "$(PERF_CLASSES)" in ""|*Create*|*Plan*|*Upload*) \
		test -n "$$PERF_ALLOW_WRITES" || { echo "PERF_CLASSES='$(PERF_CLASSES)' would write real data on dev (empty = every scenario); set PERF_ALLOW_WRITES=1 to confirm"; exit 1; };; \
	esac
	@$(MAKE) --no-print-directory perf-load PERF_HOST=$(PERF_DEV_HOST) PERF_DB_URL= PERF_USERS_FILE=/dev/null PERF_TAG=dev_$(PERF_TAG)

# One command per config under test: warm-up, then each PERF_LADDER stage,
# PERF_LADDER_COOLDOWN s apart. The cooldown stays well under the HPA's
# default 300 s scale-down stabilization so the fleet stays warm.
PERF_LADDER ?= 100 600
PERF_LADDER_TIME ?= 3m
PERF_LADDER_TAG ?=
PERF_LADDER_WARMUP_USERS ?= 50
PERF_LADDER_WARMUP_TIME ?= 60s
PERF_LADDER_COOLDOWN ?= 60
PERF_LADDER_TARGET ?= perf-dev
# perf-dev writes its reports as dev_<PERF_TAG>.
PERF_LADDER_PREFIX ?= $(if $(filter perf-dev,$(PERF_LADDER_TARGET)),dev_,)

.PHONY: perf-ladder
perf-ladder: ## Warm-up + stages for one config, then perf-summary: make perf-ladder PERF_LADDER_TAG=pool70_base [PERF_LADDER="100 600"]
	@test -n "$(PERF_LADDER_TAG)" || { echo "PERF_LADDER_TAG is required: name the config under test, e.g. PERF_LADDER_TAG=pool70_base"; exit 1; }
	@$(MAKE) --no-print-directory $(PERF_LADDER_TARGET) PERF_USERS=$(PERF_LADDER_WARMUP_USERS) \
		PERF_TIME=$(PERF_LADDER_WARMUP_TIME) PERF_TAG=$(PERF_LADDER_TAG)_warmup
	@tags=""; \
	for u in $(PERF_LADDER); do \
		echo "perf-ladder: cooldown $(PERF_LADDER_COOLDOWN) s before $$u users"; \
		sleep $(PERF_LADDER_COOLDOWN); \
		$(MAKE) --no-print-directory $(PERF_LADDER_TARGET) PERF_USERS=$$u \
			PERF_TIME=$(PERF_LADDER_TIME) PERF_TAG=$(PERF_LADDER_TAG)_$$u || exit 1; \
		tags="$$tags $(PERF_LADDER_PREFIX)$(PERF_LADDER_TAG)_$$u"; \
	done; \
	tags="$${tags# }"; \
	cmd="make perf-summary PERF_SUMMARY_TAGS=\"$$tags\""; \
	if [ -z "$$GRAFANA_SESSION$$GRAFANA_TOKEN" ]; then \
		echo "perf-ladder: no GRAFANA_SESSION/GRAFANA_TOKEN; run later from backend/: $$cmd"; exit 0; \
	fi; \
	echo "perf-ladder: waiting $(PERF_LADDER_COOLDOWN) s for the OTel export to catch up"; \
	sleep $(PERF_LADDER_COOLDOWN); \
	$(MAKE) --no-print-directory perf-summary PERF_SUMMARY_TAGS="$$tags" || \
		{ echo "perf-ladder: summary failed, stage reports are saved; rerun: $$cmd"; exit 1; }

# Prometheus through the dev Grafana's datasource proxy. Auth comes only from
# the environment: GRAFANA_SESSION (browser cookie) or GRAFANA_TOKEN.
GRAFANA_URL ?= https://grafana-dev-route-grafana-dev.apps.ocpitsd0001.xaas.epfl.ch
GRAFANA_DATASOURCE_UID ?= 73a57e8b-7679-4a18-915c-292f143448c7
PERF_NAMESPACE ?= svc1751d-co2-calculator-dev
PERF_SUMMARY_TAGS ?=

.PHONY: perf-summary
perf-summary: ## Backend CPU ms/request per stage from Prometheus: make perf-summary PERF_SUMMARY_TAGS="dev_x_100 dev_x_600"
	@test -n "$(PERF_SUMMARY_TAGS)" || { echo "PERF_SUMMARY_TAGS is required, e.g. PERF_SUMMARY_TAGS=\"dev_pool70_base_100 dev_pool70_base_600\""; exit 1; }
	$(UV) run python -m tests.performance.infra_summary --reports $(PERF_REPORT_DIR) \
		--grafana-url $(GRAFANA_URL) --datasource-uid $(GRAFANA_DATASOURCE_UID) \
		--namespace $(PERF_NAMESPACE) $(PERF_SUMMARY_TAGS)

.PHONY: perf-sweep
perf-sweep: ## Full #2295 ladder: admin reads 50→1000, principal module reads/plans/explore, standard uploads
	for u in 50 100 200 500 1000; do \
		$(MAKE) perf-load PERF_USERS=$$u PERF_CLASSES=ExplorerReadUser PERF_TAG=read_$$u || exit 1; \
	done
	for u in 50 100 200 500 1000; do \
		$(MAKE) perf-load PERF_USERS=$$u PERF_CLASSES=ModuleReadUser PERF_TAG=module_read_$$u || exit 1; \
	done
	for u in 10 20 30 40; do \
		$(MAKE) perf-load PERF_USERS=$$u PERF_CLASSES=PlanUser PERF_TAG=plan_$$u || exit 1; \
		$(MAKE) perf-load PERF_USERS=$$u PERF_CLASSES=ExploreCreateUser PERF_TAG=explore_create_$$u || exit 1; \
	done
	for u in 5 10 20; do \
		$(MAKE) perf-load PERF_USERS=$$u PERF_CLASSES=CsvUploadUser PERF_TAG=upload_$$u PERF_TIME=10m || exit 1; \
	done
	$(MAKE) perf-report

.PHONY: perf-report
perf-report: ## List endpoints with p95 > 1s across all recorded stages
	$(UV) run python -m tests.performance.report_slow $(PERF_REPORT_DIR)

.PHONY: perf-capacity
perf-capacity: ## Capacity table: per stage requests/failures/p95 + peak backend & postgres CPU/memory
	$(UV) run python -m tests.performance.resource_sampler --summarize --reports $(PERF_REPORT_DIR)

.PHONY: perf-table-matrix
perf-table-matrix: ## Sweep the table endpoint: every submodule × limit × sort column × order (+filter, deep pages, items, charts)
	$(UV) run python -m tests.performance.table_matrix \
		--host $(PERF_HOST) \
		--user "$${PERF_MATRIX_USER:-$$(psql "$(PERF_DB_URL)" -tAc "select u.institutional_id from users u join unit_users uu on uu.user_id=u.id join units un on un.id=uu.unit_id where un.institutional_code='U00000' and u.roles_raw::text like '%principal%' limit 1" 2>/dev/null | tr -d '[:space:]')}"

.PHONY: perf-db-dump
perf-db-dump: ## Dump the seeded backdrop DB for reuse (PERF_DB_URL override)
	@mkdir -p $(dir $(PERF_DUMP))
	pg_dump --format=custom --file=$(PERF_DUMP) "$(PERF_DB_URL)"
	@ls -lh $(PERF_DUMP)

.PHONY: perf-db-restore
perf-db-restore: ## Restore a previously dumped backdrop (drops current objects first)
	pg_restore --clean --if-exists --no-owner --dbname="$(PERF_DB_URL)" $(PERF_DUMP)

.PHONY: dev
dev: install ## Start backend development server
	@if [ ! -f .env ]; then \
		echo "❌ .env not found! Creating from .env.example..."; \
		cp .env.example .env; \
		echo "⚠️  Update .env with your configuration"; \
		exit 1; \
	fi
	@echo "Starting backend development server..."
	$(UV) run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: dev
run: dev ## Alias for dev

.PHONY: run-prod
run-prod: ## Run production server
	$(UV) run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

.PHONY: build
build: ## Build Docker image
	docker build -t co2-calculator-backend .

# =============================================================================
# Database
# =============================================================================

.PHONY: db-migrate
db-migrate: ## Run database migrations (upgrade to head)
	uv run alembic upgrade head

.PHONY: test-db-migrate
test-db-migrate: ## Smoke-test `db-create + db-migrate` against a docker postgres
	$(PYTEST) tests/integration/test_alembic_migrations.py -vv

.PHONY: db-downgrade
db-downgrade: ## Downgrade database to previous revision (usage: make db-downgrade revision="-1")
	uv run alembic downgrade -1

.PHONY: db-revision
db-revision: ## Create new migration (usage: make db-revision message="description")
	uv run alembic revision --autogenerate -m "$(message)"

.PHONY: db-drop
db-drop: ## Drop the database named in .env (refuses non-local hosts; add ARGS=--allow-remote on purpose)
	uv run -m scripts.manage_db --action drop $(ARGS) || true
.PHONY: db-create
db-create: ## Create the database named in .env (refuses non-local hosts; add ARGS=--allow-remote on purpose)
	uv run -m scripts.manage_db --action create $(ARGS) || true

.PHONY: formula-version
formula-version: ## Update formula version (SHA1) in .env and .env.example
	@sed -i '' "s/^FORMULA_VERSION_SHA256_SHORT=.*/FORMULA_VERSION_SHA256_SHORT=$$(git rev-parse HEAD)/" .env .env.example
	@echo "Current formula version (SHA256 short hash): $$(git rev-parse HEAD)"

.PHONY: erd
erd: ## Generate Mermaid ERD diagram from SQLAlchemy models
	uv run -m  app.generate_mermaid_erd > ../docs/src/database/erd.md ## Generate Mermaid ERD diagram from SQLAlchemy models

.PHONY: gen-emission-taxonomy
gen-emission-taxonomy: ## Generate frontend emission-taxonomy constant from EmissionType
	uv run -m app.generate_emission_taxonomy_ts > ../frontend/src/types/emission-taxonomy.gen.ts

.PHONY: gen-module-constants
gen-module-constants: ## Generate frontend module lookup constants (submodule ids, currencies, room types, cabin classes, SIUS codes)
	uv run -m app.generate_module_constants_ts > ../frontend/src/types/module-lookups.gen.ts
	cd ../frontend && npx prettier --write src/types/module-lookups.gen.ts

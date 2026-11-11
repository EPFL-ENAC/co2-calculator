---
status: in-progress
issue: "500"
last_updated: 2026-11-11
summary: Moves the institution identity out of the frontend code into one APP_INSTITUTION_* block of the runtime configuration. The block holds the name, logo, accent color, contact email and documentation links. The work breakdown splits the open work into high, medium and low priority, with estimates.
---

# 500 — Institution-specific configuration

## Goal

Another institution can run the same frontend image and show its own name,
logo and color. It sets environment variables and changes no code.

## What shipped

One block of `APP_INSTITUTION_*` variables. The frontend reads them at
startup from `/injectEnv.js`, the same chain as `APP_SENTRY_DSN`. In
`quasar dev` they come from `frontend/.env.local`.

| Variable                                    | If empty                         | Used for                                             |
| ------------------------------------------- | -------------------------------- | ---------------------------------------------------- |
| `APP_INSTITUTION_NAME`                      | Required                         | `%institution%` in texts, page title                 |
| `APP_INSTITUTION_NAME_FR_DE`                | Required                         | `%institution_fr_de%` in French texts                |
| `APP_INSTITUTION_NAME_FR_A`                 | Required                         | `%institution_fr_a%` in French texts                 |
| `APP_INSTITUTION_ID_LABEL`                  | Required                         | Headcount labels, `%institution_id_label%`           |
| `APP_INSTITUTION_ACCENT_COLOR`              | The EPFL red of the SCSS tokens  | Buttons, tabs, links, chart highlights               |
| `APP_INSTITUTION_CONTACT_EMAIL`             | Required                         | `%contact_email%` in help texts                      |
| `APP_INSTITUTION_STRATEGY_URL`              | Required                         | Home page link, English                              |
| `APP_INSTITUTION_STRATEGY_URL_FR`           | Required                         | Home page link, French                               |
| `APP_INSTITUTION_USER_DOC_URL`              | Required                         | `%user_doc_url%`, root of the user documentation     |
| `APP_INSTITUTION_BACKOFFICE_DOC_URL`        | Required                         | `%backoffice_doc_url%`, root of the back-office docs |
| `APP_INSTITUTION_ACCESS_PROVIDER_NAME`      | The link is hidden               | Access popover, name of the access portal            |
| `APP_INSTITUTION_ACCESS_PROVIDER_URL`       | The link is hidden               | Access popover, portal link                          |
| `APP_INSTITUTION_ACCESS_PROVIDER_ABOUT_URL` | The link is hidden               | Access popover, "About" link                         |
| `APP_INSTITUTION_ROLES_DOC_URL`             | The link is hidden               | Access popover, page that explains the roles         |
| `APP_INSTITUTION_EQUIPMENT_FEEDBACK_EMAIL`  | No feedback email                | Equipment "power feedback" email                     |
| `APP_INSTITUTION_MATOMO_URL`                | Required when the site id is set | Matomo analytics server                              |
| `APP_INSTITUTION_MATOMO_SITE_ID`            | Tracking is off                  | Matomo site of this instance                         |
| `APP_INSTITUTION_PRODUCTION_URL`            | Required in demo mode            | Production link of the demo notice                   |

The variables are documented in `frontend/.env.example` and listed in
`helm/values.yaml` under `frontend.env`.

### Institution assets folder

The logo, the icons, the login illustration and the fonts are files, not
variables. The image ships none of them. Each deployment mounts its folder at
`/usr/share/nginx/html/institution`, and the app loads the files from
`/institution/`. The EPFL folder is `frontend/institution/epfl`.

| File                     | Used for                                             |
| ------------------------ | ---------------------------------------------------- |
| `logo.svg`               | Header, login card, printed report                   |
| `favicon.ico`            | Browser tab icon, also served at `/favicon.ico`      |
| `apple-touch-icon.png`   | Home screen icon                                     |
| `login-illustration.svg` | Background of the login page                         |
| `fonts.css`              | Webfont declarations and `--institution-font-family` |

- `docker/check-institution-assets.sh` runs at container startup. A missing
  file stops the container and the log names it.
- Docker Compose mounts `frontend/institution/epfl`. The Helm chart mounts
  `frontend.institutionAssets.volume`, for example a ConfigMap.
- `quasar dev` serves the folder named by `INSTITUTION_ASSETS_DIR`
  (`scripts/institution-assets-plugin.js`). The browser tests serve the EPFL
  folder (`tests/integration/setup/test.ts`).
- The CO2 badge of the build does not count these files, because they are
  not part of the build.

### Observability switches

Each observability service is off until a deployment turns it on.

| Service       | Component          | Switch                                         |
| ------------- | ------------------ | ---------------------------------------------- |
| GlitchTip     | Frontend           | `APP_SENTRY_DSN`, empty is off                 |
| Matomo        | Frontend           | `APP_INSTITUTION_MATOMO_SITE_ID`, empty is off |
| OpenTelemetry | Backend and worker | Helm `backend.observability.otel.enabled`      |
| Loki          | Backend and worker | Helm `backend.observability.loki.enabled`      |
| Elasticsearch | Backend and worker | Helm `backend.elasticsearch.enabled`           |

- The Helm chart writes `OTEL_SDK_DISABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT`,
  `OTEL_EXPORTER_OTLP_PROTOCOL`, `OTEL_SERVICE_NAME`, `LOKI_ENABLED`,
  `LOKI_URL` and `LOKI_TENANT_ID` for both pods
  (`co2-calculator.backendObservabilityEnv`).
- An enabled service without its endpoint fails the Helm render.
- The backend also stops at startup when `LOKI_ENABLED` is true without
  `LOKI_URL` (`assert_observability_settings`).
- The Elasticsearch audit export (OPDo) is off by default. Off, the chart
  renders no Elasticsearch secret key and no CA volume, and audit records
  stay pending in the database. On, the backend stops at startup without
  the hosts, index, ID, API key and CA file (`assert_elasticsearch_settings`).
  The EPFL deployments must set `backend.elasticsearch.enabled: true`.
- OpenTelemetry was always on before. A deployment that exports traces must
  now set `backend.observability.otel.enabled: true` and the endpoint. It
  must also remove any `OTEL_EXPORTER_OTLP_ENDPOINT` from `backend.env` and
  `worker.env`, or the pod gets the variable twice.

### Decisions

- **No implicit state.** No institution value has a code default. A required
  variable that is empty stops the startup, and the page names it
  (`src/config/requiredConfig.ts`). An optional one turns its feature off.
  The backend follows the same rule: `DB_URL` and `FRONTEND_URL` have no
  default. The tests inject the EPFL values (`frontend/tests/runtimeEnv.ts`).
  This replaces the first decision of this issue, which kept the EPFL values
  as code defaults.
- **Texts use `%token%` placeholders.** At message load,
  `src/i18n/index.ts` replaces each token one time. No `t()` call passes the institution as a
  parameter. An unknown token throws at load, so a typo is visible.
- **French needs its own forms.** The article depends on the name
  ("de l'EPFL" but "du CERN"). English uses the short name without an article.
- **One prefix for all institution variables.** Eight variables existed
  before this issue under other names. They now use the `APP_INSTITUTION_`
  prefix, and the old names no longer work. See "Renamed variables" below.
- **One accent color.** The red SCSS tokens are now accent tokens
  (`$tokens-colors-accent*`). Each one is a CSS custom property with the EPFL
  color as fallback. `src/boot/institution.ts` sets `--institution-accent` and
  derives the hover and highlight shades with `color-mix()`. An accent token
  is not a Sass color: use `color-mix()` on it, not `rgba()`.
- **The page title is set at startup.** `index.html` holds "CO2 Calculator".
  The boot file sets "<name> CO2 Calculator".

### Files

| File                                                      | Change                                                 |
| --------------------------------------------------------- | ------------------------------------------------------ |
| `frontend/src/config/runtime.ts`                          | `runtimeConfig.institution` block                      |
| `frontend/quasar.config.js`, `frontend/src/env.d.ts`      | Declare the variables for `quasar dev`                 |
| `frontend/src/utils/institutionTokens.ts`                 | Token replacement and escape for vue-i18n              |
| `frontend/src/i18n/index.ts`, `frontend/src/i18n/*.ts`    | Tokens replace 117 hardcoded mentions                  |
| `frontend/src/utils/institutionBranding.ts`               | Accent properties, title, favicon                      |
| `frontend/src/boot/institution.ts`                        | Applies the branding before the first render           |
| `frontend/src/config/institutionLogo.ts`                  | Configured logo URL, or the bundled EPFL logo          |
| `frontend/src/css/02-tokens/*`                            | Red tokens renamed to accent tokens with CSS variables |
| `frontend/tests/unit/institution-tokens.spec.ts`          | Helpers, and a scan that keeps `src/i18n` free of EPFL |
| `frontend/tests/integration/institution-branding.spec.ts` | Rebrand through `/injectEnv.js` in a real browser      |

## Work breakdown

The lead developer reviewed the first delivery on 2026-11-11 and listed more
work. This section splits all open work into three priorities: high, medium and low. The estimates are in developer days. They include tests and review. They do not include changes
in the ops repository or a trial run by a second institution.

Two review points change the shipped work:

- **No implicit state.** The configuration comes only from the environment,
  as the [twelve-factor method](https://12factor.net/) requires. A missing
  value either stops the startup with a clear message or turns the feature
  off. A hidden EPFL value is not permitted.
- **Files, not URLs, for the assets.** The logo, the favicon, the login
  illustration and the fonts come from a mounted directory. Docker Compose
  mounts a volume. The Helm chart mounts a ConfigMap or a volume.

### High priority

An institution cannot run the app without these items.

| Work                                                                                                                                                                                                                                                | Kind       | Days       |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ---------- |
| Remove the EPFL defaults from `runtime.ts`, `helm/values.yaml` and the backend configuration (`DB_URL` SQLite file, `FRONTEND_URL`, Elasticsearch host). Each variable is required or turns its feature off.                                        | Infra      | 1 to 1.5   |
| Serve the logo, favicon, login illustration and font CSS from `/usr/share/nginx/html/institution/`. Mount it in Compose and Helm. Remove `APP_INSTITUTION_LOGO_URL` and `_FAVICON_URL`. Stop the build-time font load from `enac-it-fonts.epfl.ch`. | UI, Infra  | 1 to 2     |
| Observability switches as named Helm values for the backend and the worker: OpenTelemetry on or off (`OTEL_SDK_DISABLED`), OTLP endpoint, Loki on or off and its URL. The frontend GlitchTip and Matomo switches exist already.                     | Infra      | 1 to 1.5   |
| Elasticsearch (OPDo audit export) on or off. The Helm chart cannot start today without the Elasticsearch secret keys and the CA file.                                                                                                               | Infra      | 0.5        |
| Tableau connectors on or off for the whole app. Hide the API option in the frontend. Today the startup requires the connector encryption keys even without Tableau.                                                                                 | Functional | 1 to 1.5   |
| Fix the login with a generic OIDC provider. A login with `ROLE_PROVIDER_TYPE=jwt` stores zero roles today (see Findings).                                                                                                                           | Functional | 0.5        |
| Map roles from a claim of the ID token (for example `groups`), with a configurable claim name. This replaces Accred for the authorization.                                                                                                          | Functional | 1          |
| Keycloak in Docker Compose, with test users and roles, and a browser test of the login.                                                                                                                                                             | Infra      | 1 to 1.5   |
| Generic import of the units (CSV upload or command). Only Accred fills the unit table today, so an institution has no units.                                                                                                                        | Functional | 3 to 5     |
| Run the full stack with Docker Compose and fix what fails. Pass the frontend variables through an env file.                                                                                                                                         | Infra      | 1          |
| Full theme from a file at runtime. The container entrypoint writes a `theme.css` from a YAML or JSON value. About 110 option tokens become CSS variables. The deployment guide documents each token.                                                | UI, Infra  | 2.5 to 3.5 |
| Deployment guide for an institution: variables, assets directory, switches.                                                                                                                                                                         | Docs       | 1          |

### Medium priority

An institution can start without these items, but it meets EPFL leftovers or fixed rules.

| Work                                                                                                                                                                                           | Kind           | Days     |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------- | -------- |
| Make the unit levels a configuration. The code fixes level 4 as the workspace and levels 2 and 3 as back-office affiliations.                                                                  | Functional     | 2 to 3   |
| Tableau on or off per module (professional travel, headcount, research facilities). The CSV upload stays.                                                                                      | Functional     | 0.5 to 1 |
| ECB exchange rates on or off. With the switch off, non-EUR amounts get a clear error.                                                                                                          | Functional     | 0.5      |
| Neutral texts instead of "managed via Accred", and the "Accred unavailable" login message.                                                                                                     | UX             | 0.5      |
| SIUS codes from the backend. The frontend bundles its own copy today, so the two lists can drift.                                                                                              | Functional     | 1 to 1.5 |
| Small EPFL leftovers: links on `LogsPage.vue`, GitHub source links, the fixed ENAC-IT4R answer of `unit_results.py`, the `@epfl.ch` email fallback, and the `EPFL_TABLEAU` rename (migration). | UI, Functional | 1 to 1.5 |

### Low priority

| Work                                                                                          | Kind       | Days     |
| --------------------------------------------------------------------------------------------- | ---------- | -------- |
| Exchange rates from a stored table with a CSV upload, instead of the ECB API.                 | Functional | 2 to 4   |
| GlitchTip in the backend and the worker. Today only the frontend sends errors.                | Infra      | 0.5 to 1 |
| Prometheus metrics endpoint and example alert rules. The repository has no alert rules today. | Infra      | 1 to 2   |

### Not in this issue

- Rename the "epfl" code identifiers (`ReductionObjectiveEpflView.vue`, the
  `results_objectives_epfl_*` keys). Users do not see them.
- Several institutions in one instance. Each institution runs its own
  deployment.

### Totals

| Priority | Days         |
| -------- | ------------ |
| High     | 14.5 to 20.5 |
| Medium   | 5.5 to 8     |
| Low      | 3.5 to 7     |
| All      | 23.5 to 35.5 |

### Findings

The audit of 2026-11-11 found these facts. They drive the estimates.

- **JWT login stores no roles.** The callback in
  `backend/app/api/v1/auth.py:379-399` reads the roles from
  `get_user_by_user_id`. The JWT provider returns `{}` there
  (`backend/app/providers/role_provider.py:224-227`). Its `get_roles` parses
  the claims, but only a test route calls it.
- **Units come only from Accred.** `DatabaseUnitProvider.fetch_all_units`
  raises `NotImplementedError`. Level 4 is the workspace in
  `backend/app/services/unit_service.py:61`. Levels 2 and 3 are the
  affiliations in `backend/app/api/v1/backoffice_reporting.py:51`. The
  `path_lvl2`, `path_lvl3` and `path_lvl4` filters assume this depth.
- **The Helm chart requires Elasticsearch.** The secret references and the CA
  volume in `helm/templates/_helpers.tpl` are not optional.
- **The startup requires the connector keys.** `assert_security_settings` in
  `backend/app/main.py:58-80` stops the backend without
  `CREDENTIALS_ENCRYPTION_KEY`, its salt and `CONNECTOR_ALLOWED_HOST_SUFFIXES`.
- **ECB has no switch and no stored rates.** An ECB outage gives a 422 error
  in the planner for non-EUR purchases.
- **OpenTelemetry is always on.** The image starts with
  `opentelemetry-instrument`. The chart sets no OTLP endpoint and does not
  expose `OTEL_SDK_DISABLED`.
- **Docker Compose passes four frontend variables.** The `APP_INSTITUTION_*`
  block cannot reach the container without an edit of the compose file.

## Renamed variables

Eight frontend variables existed before this issue. They hold institution
values too, so they now use the `APP_INSTITUTION_` prefix. The frontend no
longer reads the old names. Before you deploy this change, rename the keys
in the ops repository overlays and in your `frontend/.env.local`.

| Old name                                   | New name                                    |
| ------------------------------------------ | ------------------------------------------- |
| `APP_ACCESS_MANAGEMENT_PROVIDER_NAME`      | `APP_INSTITUTION_ACCESS_PROVIDER_NAME`      |
| `APP_ACCESS_MANAGEMENT_PROVIDER_URL`       | `APP_INSTITUTION_ACCESS_PROVIDER_URL`       |
| `APP_ACCESS_MANAGEMENT_PROVIDER_ABOUT_URL` | `APP_INSTITUTION_ACCESS_PROVIDER_ABOUT_URL` |
| `APP_ROLES_DOC_URL`                        | `APP_INSTITUTION_ROLES_DOC_URL`             |
| `APP_EQUIPMENT_POWER_FEEDBACK_EMAIL`       | `APP_INSTITUTION_EQUIPMENT_FEEDBACK_EMAIL`  |
| `APP_MATOMO_URL`                           | `APP_INSTITUTION_MATOMO_URL`                |
| `APP_MATOMO_SITE_ID`                       | `APP_INSTITUTION_MATOMO_SITE_ID`            |
| `APP_PRODUCTION_URL`                       | `APP_INSTITUTION_PRODUCTION_URL`            |

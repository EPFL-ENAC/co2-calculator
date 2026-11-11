---
status: in-progress
issue: "500"
last_updated: 2026-11-11
summary: Moves the institution identity out of the frontend code into one APP_INSTITUTION_* block of the runtime configuration. The block holds the name, logo, accent color, contact email and documentation links. EPFL values stay the code defaults. SIUS codes and some EPFL-only items remain.
---

# 500 — Institution-specific configuration

## Goal

Another institution can run the same frontend image and show its own name,
logo and color. It sets environment variables and changes no code.

## What shipped

One block of `APP_INSTITUTION_*` variables. The frontend reads them at
startup from `/injectEnv.js`, the same chain as `APP_SENTRY_DSN`. In
`quasar dev` they come from `frontend/.env.local`.

| Variable                                    | EPFL default (in code)                                       | Used for                                             |
| ------------------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------- |
| `APP_INSTITUTION_NAME`                      | `EPFL`                                                       | `%institution%` in texts, page title                 |
| `APP_INSTITUTION_NAME_FR_DE`                | `de l'EPFL`                                                  | `%institution_fr_de%` in French texts                |
| `APP_INSTITUTION_NAME_FR_A`                 | `à l'EPFL`                                                   | `%institution_fr_a%` in French texts                 |
| `APP_INSTITUTION_ID_LABEL`                  | `SCIPER`                                                     | Headcount labels, `%institution_id_label%`           |
| `APP_INSTITUTION_LOGO_URL`                  | empty (bundled EPFL logo)                                    | Header, login card, printed report                   |
| `APP_INSTITUTION_FAVICON_URL`               | empty (bundled EPFL favicon)                                 | Browser tab icon                                     |
| `APP_INSTITUTION_ACCENT_COLOR`              | empty (EPFL red of the SCSS tokens)                          | Buttons, tabs, links, chart highlights               |
| `APP_INSTITUTION_CONTACT_EMAIL`             | `co2calculator@epfl.ch`                                      | `%contact_email%` in help texts                      |
| `APP_INSTITUTION_STRATEGY_URL`              | `https://www.epfl.ch/about/sustainability/strategy/`         | Home page link, English                              |
| `APP_INSTITUTION_STRATEGY_URL_FR`           | `https://www.epfl.ch/about/sustainability/fr/strategie/`     | Home page link, French                               |
| `APP_INSTITUTION_USER_DOC_URL`              | `https://epfl-enac.github.io/co2-calculator-user-doc`        | `%user_doc_url%`, root of the user documentation     |
| `APP_INSTITUTION_BACKOFFICE_DOC_URL`        | `https://epfl-enac.github.io/co2-calculator-back-office-doc` | `%backoffice_doc_url%`, root of the back-office docs |
| `APP_INSTITUTION_ACCESS_PROVIDER_NAME`      | none (empty hides the link)                                  | Access popover, name of the access portal            |
| `APP_INSTITUTION_ACCESS_PROVIDER_URL`       | none (empty hides the link)                                  | Access popover, portal link                          |
| `APP_INSTITUTION_ACCESS_PROVIDER_ABOUT_URL` | none                                                         | Access popover, "About" link                         |
| `APP_INSTITUTION_ROLES_DOC_URL`             | none                                                         | Access popover, page that explains the roles         |
| `APP_INSTITUTION_EQUIPMENT_FEEDBACK_EMAIL`  | none                                                         | Equipment "power feedback" email                     |
| `APP_INSTITUTION_MATOMO_URL`                | `https://enac-webanalytics.epfl.ch/piwik/`                   | Matomo analytics server                              |
| `APP_INSTITUTION_MATOMO_SITE_ID`            | empty (tracking off)                                         | Matomo site of this instance                         |
| `APP_INSTITUTION_PRODUCTION_URL`            | `https://go.epfl.ch/co2`                                     | Production link of the demo notice                   |

The variables are documented in `frontend/.env.example` and listed in
`helm/values.yaml` under `frontend.env`.

### Decisions

- **EPFL values are the code defaults.** An EPFL deployment needs no change in
  the ops repository. This follows the Matomo and production URLs.
  The cost: an institution that forgets one variable shows the EPFL value.
- **Texts use `%token%` placeholders.** When the messages load,
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

## Remaining work

These items still name EPFL. Each one needs its own decision.

- **SIUS codes.** `SIUS_CODE_VALUES` is a backend constant, and the frontend
  bakes a generated copy plus a hand-written planner list into the bundle. An
  environment variable on the backend alone lets the two drift. The frontend
  must first read the codes from the backend.
- **Accred texts and link.** The user management page links to
  `accred.epfl.ch` and its texts name Accred. Reuse
  `APP_ACCESS_MANAGEMENT_PROVIDER_NAME` and `_URL` after the ops values are
  confirmed.
- **Webfont.** `index.html` and `_fonts.scss` load Suisse Intl from
  `enac-it-fonts.epfl.ch` at build time.
- **Login illustration.** The icons in `src/assets/login-img.svg` are red. An SVG
  loaded as an image cannot read a CSS variable.
- **System logs page.** `LogsPage.vue` links to the EPFL OpenShift, Argo CD
  and Grafana instances.
- **Source links.** The back-office editing pages link to the
  `EPFL-ENAC/co2-calculator` GitHub repository.
- **Backend.** The `EPFL_TABLEAU` connector type is stored in the database, so
  a rename needs a migration. Its label is "EPFL Tableau". The Accred provider
  builds a missing email with `@epfl.ch`.
- **Chart component names.** `ReductionObjectiveEpflView.vue` and the
  `results_objectives_epfl_*` keys keep "epfl" in code identifiers only.

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

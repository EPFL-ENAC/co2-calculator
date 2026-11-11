# Institution Configuration Reference

This page lists every value that an institution sets to run the CO2
calculator: the variables, the files and the switches. The procedure is in
[Deploy for another institution](08-deploy-for-an-institution.md). The
`.env.example` files show the EPFL values.

## Frontend variables

The frontend container writes its `APP_*` variables to `/injectEnv.js` at
startup. An empty required variable stops the app, and the page names it.

| Variable                                    | Required          | Used for                                                       |
| ------------------------------------------- | ----------------- | -------------------------------------------------------------- |
| `APP_INSTITUTION_NAME`                      | Yes               | Short name in the texts and the page title, for example `EPFL` |
| `APP_INSTITUTION_NAME_FR_DE`                | Yes               | French form with "de", for example `de l'EPFL`                 |
| `APP_INSTITUTION_NAME_FR_A`                 | Yes               | French form with "à", for example `à l'EPFL`                   |
| `APP_INSTITUTION_ID_LABEL`                  | Yes               | Label of the member identifier, for example `SCIPER`           |
| `APP_INSTITUTION_CONTACT_EMAIL`             | Yes               | Support address in the help texts                              |
| `APP_INSTITUTION_STRATEGY_URL`              | Yes               | Sustainability strategy page, English                          |
| `APP_INSTITUTION_STRATEGY_URL_FR`           | Yes               | Sustainability strategy page, French                           |
| `APP_INSTITUTION_USER_DOC_URL`              | Yes               | Root of the user documentation, no trailing slash              |
| `APP_INSTITUTION_BACKOFFICE_DOC_URL`        | Yes               | Root of the back-office documentation, no trailing slash       |
| `APP_INSTITUTION_ACCESS_PROVIDER_NAME`      | Yes               | Name of the portal where roles are delegated                   |
| `APP_INSTITUTION_ACCESS_PROVIDER_URL`       | No, empty hides   | Link to that portal                                            |
| `APP_INSTITUTION_ACCESS_PROVIDER_ABOUT_URL` | No, empty hides   | "About" page of that portal                                    |
| `APP_INSTITUTION_ROLES_DOC_URL`             | No, empty hides   | Page that explains the roles                                   |
| `APP_INSTITUTION_EQUIPMENT_FEEDBACK_EMAIL`  | No                | Recipient of the equipment power feedback                      |
| `APP_INSTITUTION_MATOMO_URL`                | With a site id    | Matomo server                                                  |
| `APP_INSTITUTION_MATOMO_SITE_ID`            | No, empty is off  | Matomo site of this instance                                   |
| `APP_SENTRY_DSN`                            | No, empty is off  | GlitchTip project of the frontend                              |
| `APP_SYSTEM_LINKS`                          | No, empty is none | Operations links of the system logs page, a JSON array         |
| `APP_SOURCE_REPOSITORY_URL`                 | No, empty hides   | Source repository linked from the texts editing page           |
| `APP_INSTITUTION_PRODUCTION_URL`            | In demo mode      | Production instance that the demo notice links to              |

## Assets folder

Mount the folder at `/usr/share/nginx/html/institution`. A missing file
stops the container, and the log names it.

| File                     | Used for                                                  |
| ------------------------ | --------------------------------------------------------- |
| `logo.svg`               | Header, login card, printed report                        |
| `favicon.ico`            | Browser tab icon                                          |
| `apple-touch-icon.png`   | Home screen icon                                          |
| `login-illustration.svg` | Background of the login page                              |
| `fonts.css`              | `@font-face` rules and `--institution-font-family`        |
| `theme.env`              | Colors and border radii, one `token=value` line per token |

Give the font files names without a dash followed by eight letters or
digits. nginx caches such names for a year, as build output.

## Theme tokens

`theme.env` must set `colors-accent`. A token that the file leaves out
keeps the base design. The hover and highlight shades of the accent derive
from it unless the file sets them. An unknown token stops the app with its
line number. The full list is `THEME_TOKENS` in
`frontend/src/utils/institutionTheme.ts`:

- Accent: `colors-accent`, `colors-accent-hover`,
  `colors-accent-highlight`, `colors-accent-highlight-strong`.
- Base: `colors-base-black`, `colors-base-white`, `colors-leman`,
  `colors-canard`, `colors-validated-highlight`.
- Status: `colors-status-green`, `colors-status-red`,
  `colors-status-yellow`.
- Greys: `colors-grey-scale-grey-100` to `colors-grey-scale-grey-600`.
- Radii: `border-radius-generic-border-radius`,
  `border-radius-generic-border-radius-px`,
  `border-radius-full-border-radius`, `border-radius-lg-border-radius`.

## Backend variables

With an empty required variable, the backend stops at startup.

| Variable                                                     | Required        | Used for                                             |
| ------------------------------------------------------------ | --------------- | ---------------------------------------------------- |
| `DB_URL`                                                     | Yes             | PostgreSQL connection                                |
| `FRONTEND_URL`                                               | Yes             | Public URL of the frontend, for the login redirects  |
| `OAUTH_ISSUER_URL`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET` | Yes             | OpenID Connect client                                |
| `ROLE_PROVIDER_TYPE`                                         | Yes             | `jwt` for roles in the token, `accred` at EPFL       |
| `JWT_ROLES_CLAIM`                                            | No, `roles`     | Token claim with the roles, `groups` for Keycloak    |
| `UNIT_PROVIDER_TYPE`                                         | Yes             | `database` for a units CSV file, `accred` at EPFL    |
| `UNITS_CSV_PATH`                                             | With `database` | Units CSV file                                       |
| `UNIT_WORKSPACE_LEVEL`                                       | Yes             | Level of the units that own a workspace, `4` at EPFL |
| `UNIT_AFFILIATION_LEVELS`                                    | Yes             | Levels offered as affiliations, `2,3` at EPFL        |
| `EXCHANGE_RATES_SOURCE`                                      | Yes             | `ecb` for the ECB rates, `none` for EUR only         |
| `JWT_HMAC_KEY`, `SESSION_HMAC_KEY`                           | Yes             | Session signing keys, `openssl rand -hex 32`         |
| `FILES_ENCRYPTION_KEY`, `FILES_ENCRYPTION_SALT`              | Yes             | Encryption of the uploaded files                     |

## Units CSV file

One row per unit. Each unit names its parent, and the root has level 1.

```csv
institutional_code,institutional_id,name,level,parent_institutional_code,label_en,label_fr,is_active
10000,10000,UNIV,1,,Test University,Université test,true
12345,12345,LAB-TEST,2,10000,Test Laboratory,Laboratoire de test,true
```

- `institutional_id` is the id that the role claims name.
- `label_en`, `label_fr` and `is_active` are optional.
- A duplicate code, a missing parent, a loop or a wrong level fails the
  unit sync, and the error names the row.

`keycloak/units.csv` is a complete example.

## Switches

Each service is off until you turn it on.

| Service                    | Switch                                                        | When on, it also needs                                        |
| -------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------- |
| Tableau import             | `TABLEAU_MODULES`, Helm `backend.tableau.modules`             | `CREDENTIALS_ENCRYPTION_*`, `CONNECTOR_ALLOWED_HOST_SUFFIXES` |
| Elasticsearch audit export | `ELASTICSEARCH_ENABLED`, Helm `backend.elasticsearch.enabled` | Hosts, index, ID, API key, CA file                            |
| OpenTelemetry              | Helm `backend.observability.otel.enabled`                     | `endpoint`                                                    |
| Loki                       | Helm `backend.observability.loki.enabled`                     | `url`                                                         |
| ECB exchange rates         | `EXCHANGE_RATES_SOURCE=ecb`                                   | Access to the ECB API                                         |
| Matomo                     | `APP_INSTITUTION_MATOMO_SITE_ID`                              | `APP_INSTITUTION_MATOMO_URL`                                  |
| GlitchTip, frontend        | `APP_SENTRY_DSN`                                              | Nothing more                                                  |

`TABLEAU_MODULES` lists the modules that import from Tableau:
`professional_travel`, `headcount`, `research_facilities`. Empty turns
Tableau off for the whole app, and the CSV upload stays.

## Next step

Follow the steps of [Deploy for another institution](08-deploy-for-an-institution.md).

---
status: in-progress
issue: 3244
last_updated: 2026-11-12
summary: "Institution name, texts, documentation links, logo, fonts and color theme come from the deployment. The code has no EPFL default and the texts do not name Accred. A CI check finds hard-coded EPFL, Accred or Entra."
---

# Institution values, assets and theme from the deployment (#3244)

Part 1 of 5 of #500. Another institution runs the same images. It sets
environment values and mounts one folder of files. It changes no code.

## Decisions

- The operations links of the system logs page stay in the app. Each link
  is one value, and an empty value hides the link (decided on the issue).
- Each deployment shows only its own operations links. The page no longer
  lists the links of the three EPFL clusters on every deployment.
- The frontend reads every `APP_*` value from `window.injectedEnvVariable`
  only. The `import.meta.env` fallback goes away. `quasar dev`, `vite
preview`, the component tests and Storybook get `injectEnv.js` and
  `theme.css` from the same `docker/entrypoint.sh` and
  `docker/institution.sh` as the container, through
  `frontend/build/institution.mjs`. `APP_VERSION` and `APP_BUILD_TIME` stay
  build-time values, because they identify the bundle.
- The tab title is set at runtime from the text `app_document_title`,
  because it names the institution.
- The theme file sets CSS custom properties. The SCSS tokens read
  `var(--theme-*)`, so one image serves every institution.

## Values

Required values. If one is empty, the app shows the missing-values page
instead of the app, with the names of the empty values.

| Value                                        | EPFL                          |
| -------------------------------------------- | ----------------------------- |
| `APP_INSTITUTION_NAME`                       | `EPFL`                        |
| `APP_INSTITUTION_NAME_FR_DE`                 | `de l'EPFL`                   |
| `APP_INSTITUTION_NAME_FR_A`                  | `à l'EPFL`                    |
| `APP_INSTITUTIONAL_ID_LABEL`                 | `SCIPER`                      |
| `APP_CONTACT_EMAIL`                          | the support address           |
| `APP_USER_DOC_URL`                           | the user documentation        |
| `APP_BACKOFFICE_DOC_URL`                     | the back-office documentation |
| `APP_STRATEGY_URL_EN`, `APP_STRATEGY_URL_FR` | the climate strategy page     |

Optional values. An empty value hides the link that uses it.

- Access tool: `APP_ACCESS_MANAGEMENT_URL`,
  `APP_ACCESS_MANAGEMENT_ABOUT_URL`, `APP_ROLES_DOC_URL`. The old
  `APP_ACCESS_MANAGEMENT_PROVIDER_NAME` goes away: no value names the tool.
- Sources: `APP_SOURCE_CODE_URL`, `APP_USER_DOC_SOURCE_URL`,
  `APP_BACKOFFICE_DOC_SOURCE_URL`, `APP_DEVELOPER_DOC_URL`.
- Operations: `APP_OPS_ARGOCD_URL`, `APP_OPS_GRAFANA_DASHBOARD_URL`,
  `APP_OPS_GRAFANA_GRAPHS_URL`, `APP_OPS_LOGS_URL`, `APP_OPS_OPENSHIFT_URL`.

Two values lose their EPFL default. If `APP_MATOMO_SITE_ID` is set,
`APP_MATOMO_URL` is required. If `APP_DEMO_MODE` is `true`,
`APP_PRODUCTION_URL` is required. The backend loses its defaults for `DB_URL`
and `FRONTEND_URL`.

The EPFL values are in `institutions/epfl/frontend.env.example`. A
developer copies it to `frontend.env`, which git ignores. If the file is
missing, `make install` copies it. Docker Compose and the dev server read
`frontend.env`. The tests read the example, so CI and local runs use the
same values. The clusters get the same values from the ops repository.

The dev server needs two paths in `frontend/.env.local`:
`INSTITUTION_ENV_FILE` and `INSTITUTION_ASSETS_DIR`. See
`frontend/.env.example`.

## Texts

The English and French texts hold placeholders, for example
`%institution%`. When `src/i18n/index.ts` builds the messages, it
replaces the placeholders with the values (`src/utils/i18nPlaceholders.ts`).
It escapes the characters that vue-i18n reads as syntax (`@`, `{`, `}`,
`|`, `$`). An unknown placeholder throws. The message functions of
`common.ts` hold no placeholder and stay as they are.

| Placeholder            | Value                                                             |
| ---------------------- | ----------------------------------------------------------------- |
| `%institution%`        | `APP_INSTITUTION_NAME`                                            |
| `%institution_fr_de%`  | `APP_INSTITUTION_NAME_FR_DE`                                      |
| `%institution_fr_a%`   | `APP_INSTITUTION_NAME_FR_A`                                       |
| `%institutional_id%`   | `APP_INSTITUTIONAL_ID_LABEL`                                      |
| `%contact_email%`      | `APP_CONTACT_EMAIL`                                               |
| `%user_doc_url%`       | `APP_USER_DOC_URL`                                                |
| `%backoffice_doc_url%` | `APP_BACKOFFICE_DOC_URL`                                          |
| `%strategy_url%`       | `APP_STRATEGY_URL_EN` in English, `APP_STRATEGY_URL_FR` in French |

The doc links keep their page path after the placeholder, for example
`%user_doc_url%fr/headcount/`.

No text names Accred, for every institution. The texts say "the access
management tool" and "the units directory".

The French forms give a straight apostrophe ("de l'EPFL"). A few texts had
a typographic one before. There is no "pour" form: one text now says "de
référence de l'EPFL" instead of "de référence pour l'EPFL".

## Assets folder

The container mounts the folder at `/institution`, and nginx serves it at
`/institution/` with revalidation. The files:

```
logo.svg
login-illustration.svg
favicon.ico
favicon-16x16.png  favicon-32x32.png  favicon-96x96.png  favicon-128x128.png
fonts/regular.woff2  fonts/medium.woff2  fonts/bold.woff2
theme.conf
```

`frontend/docker/institution.sh` runs at startup after `entrypoint.sh`. If
a file is missing, it exits with an error that names the file, and the
container stops. The EPFL files are in `institutions/epfl/assets/`.

The fonts of that folder are a placeholder: Geist 1.3.1 under the SIL Open
Font License, subset with `pyftsubset` to Latin-1, the usual punctuation,
`€`, `−` and `₂`. `fonts/README.md` explains the placeholder, gives the
licensing rules for that folder, and holds the license text. The license
of the EPFL brand font Suisse Int'l does not allow it in the repository.
The license of a system font such as Arial does not allow it either. The
EPFL clusters mount the licensed files through the ops repository, so local
runs and the tests show Geist, and the clusters show Suisse Int'l. Docker
Compose mounts this folder. The Helm chart mounts the volume that
`frontend.institutionAssets.volume` gives, and fails to render without it.

## Theme

`theme.conf` has one `name: value` line per value. A line that starts
with `#` is a comment. `frontend/docker/theme.awk` writes `theme.css` with
one `--theme-<name>` property per line. These lines stop the startup: an
unknown name, a line without `:`, and a value with `;`, `{`, `}` or `<`.
The message gives the line number. Only `accent` is required. The names are
listed in `theme.awk`. `scripts/check-theme-keys.mjs` makes sure that the
SCSS uses the same names.

The shades of the accent (`accent-hover`, `accent-light`,
`accent-lighter`) default to a `color-mix()` of the accent. A theme can
set them, and the EPFL theme does, so EPFL keeps its exact colors.

## Removed

- `GET /v1/unit/{unit_id}/results` and the fixed EPFL answer it returned,
  with the unused unit-results state of the workspace store.
- The `epfl-logo.svg` import, the `enac-it-fonts.epfl.ch` fonts and their
  preloads.
- Unused texts `header_documentation_link` and
  `header_dev_documentation_link`.
- `src/constant/institutionalId.ts`. The label is a value now.
- `frontend/public/injectEnv.js`. nginx and the dev server serve it.

## Renamed

- `ReductionObjectiveEpflView.vue` is now
  `ReductionObjectiveInstitutionView.vue`. The texts
  `results_objectives_*epfl*` are now `results_objectives_*institution*`.
- The font family `SuisseIntl` is now `InstitutionFont`.
- The seed input file `reduction_obj_epfl_footprint(in).csv` is now
  `reduction_obj_institution_footprint(in).csv`. The file is not in git:
  each developer renames the local copy in `backend/INPUT_DATA/`.

## CI check

If a file that git tracks or does not ignore has `EPFL`, `epfl`, `Accred`,
`ACCRED` or `Entra`, `scripts/check_institution_words.py` fails. `make
lint` runs it, and the job `institution-words` of `quality-check.yml` runs
it on each pull request. It skips the documentation (`docs/`, `*.md`).
`scripts/institution-words-allowlist.txt` lists the exceptions, each with
a reason:

- the EPFL folder `institutions/epfl/`
- the GitHub organization and the image registry of the project
- the CI/CD and team tooling of the project repository
- the immutable Alembic history
- the Accred and Entra words of the backend login and units, and the
  Accred secrets of the Helm chart, which #3246 removes
- `EPFL_TABLEAU`, which #3245 renames

## EPFL deployment (ops repository)

Before the next deployment, a human changes the ops repository:

- Rename `APP_ACCESS_MANAGEMENT_PROVIDER_URL` to
  `APP_ACCESS_MANAGEMENT_URL`.
- Rename `APP_ACCESS_MANAGEMENT_PROVIDER_ABOUT_URL` to
  `APP_ACCESS_MANAGEMENT_ABOUT_URL`.
- Delete `APP_ACCESS_MANAGEMENT_PROVIDER_NAME`.
- Set the values of `institutions/epfl/frontend.env` and the operations
  links of each cluster.
- Set `APP_MATOMO_URL` and `APP_PRODUCTION_URL` where they are used.
- Give the assets volume, for example a ConfigMap made from
  `institutions/epfl/assets/` with `binaryData`. Replace the three files of
  `fonts/` with the licensed Suisse Int'l files of the font server, under
  the same names.
- Set `FRONTEND_URL` and `DB_URL` for the backend. They have no default.

A developer also adds `FRONTEND_URL` to `backend/.env`, and the two
`INSTITUTION_*` paths to `frontend/.env.local`.

## Caveats

- The first-load badge counts only the bundle. The fonts of the
  deployment are not known at build time.
- The `institution-words` job is a required check only after an admin adds
  it to the branch protection of `dev` and `main`.

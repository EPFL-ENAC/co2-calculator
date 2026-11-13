---
status: in-progress
issue: 3244
last_updated: 2026-11-13
summary: "Institution name, texts, documentation links, logo, fonts and color theme come from the deployment. The image has neutral default assets, so a deployment gives only its values and a theme.conf. The code has no EPFL default and the texts do not name Accred. A CI check finds hard-coded EPFL, Accred or Entra."
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
- The image has a neutral default for every asset except `theme.conf`,
  as Keycloak ships its default theme (decided with the lead on
  2026-11-13). A new deployment works with its values and one theme line.
  The accent color stays required, so the folder still gives
  `theme.conf`. A default is visible on the first page, unlike a wrong
  number. The startup log names the source of each file, and an unknown
  file name stops the container, so a typo in an override is not silent.
- The fonts default to Geist in the image. `theme.conf` can point them at
  a font server. EPFL points them at `enac-it-fonts.epfl.ch`, so the
  licensed Suisse Int'l files are in no repository.

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
and `FRONTEND_URL`. The Helm default of `FRONTEND_URL` is empty, so a
cluster that does not set it stops at boot. Docker Compose takes `DB_URL`
from `backend/.env` and changes only its host from `localhost` to
`postgres`, so the credentials are written in one file.

The texts add page paths after `APP_USER_DOC_URL` and
`APP_BACKOFFICE_DOC_URL`. If one does not end with `/`, the missing-values
page lists it with the reason.

If `APP_EQUIPMENT_POWER_FEEDBACK_EMAIL` is empty, the equipment dialog has
no power request tab: a mailto link without a recipient opens an empty
draft.

The EPFL values are in `institutions/epfl/frontend.env.example`. A
developer copies it to `frontend.env`, which git ignores. If the file is
missing, `make install` copies it. Docker Compose and the dev server read
`frontend.env`. The tests read the example, so CI and local runs use the
same values. The clusters get the same values from the ops repository.

The dev server needs two paths in `frontend/.env.local`:
`INSTITUTION_ENV_FILE` and `INSTITUTION_ASSETS_DIR`. See
`frontend/.env.example`. `build/institution.mjs` loads `.env.local` for
`quasar dev` and for `npm run preview`. If a path does not exist, the error
names `make install`. `wtx` copies `frontend.env` into a new worktree, as
it copies `.env.local`.

Three builds outside the container write the institution files with the
same scripts. `npm run preview` and the Lighthouse workflow run
`build/prepare-preview.mjs` on `dist/spa`. The Storybook image gets the
EPFL folder through the named build context `institutions`, because the
folder is outside its build context `frontend/`.

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

The deployment mounts its folder at `/institution`. At startup,
`frontend/docker/institution.sh` runs after `entrypoint.sh`. It copies the
defaults of the image (`frontend/institution-default/`, in the image at
`/usr/local/share/institution/default`), then the files of the mounted
folder, to `/tmp/institution`. nginx serves that folder at
`/institution/` with revalidation. The files:

```
logo.svg
login-illustration.svg
favicon.ico
favicon-16x16.png  favicon-32x32.png  favicon-96x96.png  favicon-128x128.png
fonts/regular.woff2  fonts/medium.woff2  fonts/bold.woff2
theme.conf         (required, no default)
```

The defaults are a gray mark with a leaf for the logo and the icons, the
login illustration in gray, and Geist. The log gives the source of each
file. These cases stop the container with a message: no `theme.conf`, an
empty file, and a file name outside the list. Names that start with `.`
are skipped, because a ConfigMap mount adds `..data`. A file of `fonts/`
that is not a `.woff2` is allowed, because a free font keeps its license
next to its files. A line of `theme.conf` can end with `\r\n`.

The default fonts are Geist 1.3.1 under the SIL Open Font License, subset
with `pyftsubset` to Latin-1, the usual punctuation, `€`, `−` and `₂`.
`frontend/institution-default/fonts/README.md` gives the licensing rules
and holds the license text. The license of the EPFL brand font Suisse
Int'l does not allow it in a repository. The license of a system font such
as Arial does not allow it either.

The EPFL folder `institutions/epfl/assets/` gives the logo, the icons, the
login illustration and `theme.conf`. It has no font files. Docker Compose
mounts it. The tests mount `frontend/tests/institution/`, which holds only
`theme.conf`, so they run on the defaults. The Helm chart mounts the volume
that `frontend.institutionAssets.volume` gives, and fails to render
without it, because the volume gives `theme.conf`.

## Theme

`theme.conf` has one `name: value` line per value. A line that starts
with `#` is a comment. `frontend/docker/theme.awk` writes `theme.css` with
one `--theme-<name>` property per line. These lines stop the startup: an
unknown name, a line without `:`, and a value with `;`, `{`, `}` or `<`.
The message gives the line number. Only `accent` is required. The names are
listed in `theme.awk`, and `frontend/institution-default/theme.conf.example`
documents each one. `scripts/check-theme-keys.mjs` makes sure that the
SCSS uses the same names.

`font-regular`, `font-medium` and `font-bold` take the URL of a woff2 file:
an `https://` URL or a path that starts with `/`. `theme.awk` writes one
`@font-face` rule per weight for the family `InstitutionFont`, because
`@font-face` cannot read a custom property. Without a value, the rule loads
`/institution/fonts/<weight>.woff2`. The bundle has no `@font-face` rule,
and `index.html` preloads no font, because the URLs are known only at
startup.

The shades of the accent (`accent-hover`, `accent-light`,
`accent-lighter`) default to a `color-mix()` of the accent. A theme can
set them, and the EPFL theme does, so EPFL keeps its exact colors.

## Removed

- `GET /v1/unit/{unit_id}/results` and the fixed EPFL answer it returned,
  with the unused unit-results state of the workspace store.
- The `epfl-logo.svg` import, the `enac-it-fonts.epfl.ch` fonts of the
  bundle and the font preloads. EPFL gets the same fonts through its
  `theme.conf`.
- `src/css/00-fonts/_fonts.scss` and the `fonts` CSS layer.
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
  `institutions/epfl/assets/` with `binaryData`. The folder has no font
  files: its `theme.conf` points the fonts at the ENAC font server. Without
  font keys, the ConfigMap needs no `items` list.
- Set `FRONTEND_URL` and `DB_URL` for the backend. They have no default.

A developer also adds `FRONTEND_URL` to `backend/.env`, and the two
`INSTITUTION_*` paths to `frontend/.env.local`.

## Caveats

- The first-load badge counts only the bundle. The fonts of the
  deployment are not known at build time.
- Without the font preloads, the browser finds the fonts later, when it
  applies `theme.css`. The first text can show the fallback font a little
  longer.
- The `institution-words` job is a required check only after an admin adds
  it to the branch protection of `dev` and `main`.
- Only the browser checks the required values. A rollout with a wrong key
  starts its pods, and they show the missing-values page to every user.
  `entrypoint.sh` could check the keys at startup and stop the rollout, as
  `institution.sh` does for `theme.conf`. That needs the list of required
  keys in the shell script too. Open question, not decided.

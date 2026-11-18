---
status: in-progress
issue: 3244
last_updated: 2026-11-18
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
preview`, the component tests and Storybook get `injectEnv.js`,
  `theme.css` and the assets from the same `docker/entrypoint.sh` as the
  container, through `frontend/build/institution.mjs`. `APP_VERSION` and
  `APP_BUILD_TIME` stay build-time values, because they identify the bundle.
- One script, `frontend/docker/entrypoint.sh`, writes the values, the
  assets folder and the theme, and holds every check. It is POSIX sh with
  awk, because the nginx image has no Node and no Python.
  `build/institution.mjs` only starts it and gives its output to Vite as the
  public folder. So the repository has one parser for the values file, one
  for the theme, and no second file server.
- A wrong value stops the container, and the app has no page for it. A
  rollout with a wrong key then keeps the old pods. The browser does not
  check the values again.
- Every `APP_*` value is public, because `injectEnv.js` goes to every
  browser without a login. A key whose name has `SECRET`, `PASSWORD`,
  `TOKEN`, `CREDENTIAL` or `PRIVATE` stops the container.
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
- One folder is one institution: `values.env`, `theme.conf` and the
  assets. The repository names no institution. It holds only the neutral
  example `frontend/institution-example/`, which the dev server, the
  tests, Docker Compose and Storybook use by default. A real institution
  keeps its folder outside this repository. Before this rule, the EPFL
  data existed twice: 8 asset files and 17 values were the same in the
  app repository and the ops repository, and nothing kept them equal. A
  developer also had a fourth env file, a generic repository had a folder
  named after one institution, and that folder was outside the
  `./frontend` Docker build context.

## Values

Required values. If one is empty, `entrypoint.sh` stops the container
and the log names each empty value.

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
`postgres`, so the credentials are written in one file. Compose refuses
any other host, so a `backend/.env` that names a shared database never gets
the migrations of a local `docker compose up`.

The texts add page paths after `APP_USER_DOC_URL` and
`APP_BACKOFFICE_DOC_URL`. If one does not end with `/`, the container
stops with the reason.

If `APP_EQUIPMENT_POWER_FEEDBACK_EMAIL` is empty, the equipment dialog has
no power request tab: a mailto link without a recipient opens an empty
draft.

The values can come from the optional file `values.env` of the
institution folder, from the environment of the pod, or from both. In the
container, `entrypoint.sh` reads `/institution/values.env` when it exists,
then the environment. A variable of the environment wins over the file. So
a deployment can keep its institution values in `values.env` and set the
per-cluster values (`APP_ENVIRONMENT`, `APP_SENTRY_DSN`, `APP_MATOMO_*`,
`APP_OPS_*`) under the Helm `frontend.env`. The file holds
`APP_<NAME>=value` lines, `#` comments and literal values. Any other line
stops the script.

The dev server, the tests and Storybook read one variable,
`INSTITUTION_DIR`: a path relative to `frontend/`, or absolute. If it is
not set, they use `frontend/institution-example/` ("Example University").
So a new clone runs with `make install` alone, which copies no
institution file. To see a real institution, a developer sets
`INSTITUTION_DIR` in `frontend/.env.local`. A personal `APP_*` value in
`.env.local` still wins. `build/institution.mjs` loads `.env.local` for
`quasar dev` and for `npm run preview`, with `process.loadEnvFile` of Node.

The dev server gives the output folder of the script to Vite as its public
folder, so Vite serves `/injectEnv.js`, `/theme.css` and `/institution/` as
nginx does. When a file of the institution changes, the dev server runs the
script again and reloads the page.

Three builds outside the container write the institution files with the
same script. `npm run preview` and the Lighthouse workflow run
`build/prepare-preview.mjs` on `dist/spa`. The Storybook image copies the
example folder from its normal build context `frontend/`.

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
`frontend/docker/entrypoint.sh` copies the defaults of the image (`frontend/institution-default/`, in the image at
`/usr/local/share/institution/default`), then the files of the mounted
folder, to `/tmp/institution`. nginx serves that folder at
`/institution/` with revalidation, and with a second
`Content-Security-Policy` that stops script in a file opened as a page (an
SVG of the institution). The files:

```
values.env         (optional, see Values)
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

The example folder `frontend/institution-example/` holds only
`values.env` and `theme.conf`, so the dev server, the tests and Storybook
run on the default assets. Docker Compose mounts it at `/institution` and
has no institution `env_file`. The Helm chart mounts the volume
that `frontend.institutionAssets.volume` gives, and fails to render
without it, because the volume gives `theme.conf`.

## Theme

`theme.conf` has one `name: value` line per value. A line that starts
with `#` is a comment. `frontend/docker/entrypoint.sh` writes `theme.css`
with one `--theme-<name>` property per line. A value is pasted into CSS, so
each kind of name accepts one shape, and every other value stops the
startup. A color is a hex value (`#rgb` or `#rrggbb`, with or without
alpha). A radius is a number with `px`, `rem`, `em` or `%`. An unknown name
and a line without `:` also stop the startup. The message gives the line
number. Only `accent` is required. The names are listed in `entrypoint.sh`,
and `frontend/institution-default/theme.conf.example` documents each one.
`scripts/check-theme-keys.mjs` makes sure that the SCSS uses the same
names.

`font-regular`, `font-medium` and `font-bold` take the URL of a woff2 file:
an `https://` URL or a path that starts with one `/`. `entrypoint.sh`
writes one `@font-face` rule per weight for the family `InstitutionFont`, because
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
- The missing-values page and its checks in `src/config/runtime.ts`. The
  container checks the values at startup.

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

- the GitHub organization and the image registry of the project
- the CI/CD and team tooling of the project repository
- the immutable Alembic history
- the Accred and Entra words of the backend login and units, and the
  Accred secrets of the Helm chart, which #3246 removes
- `EPFL_TABLEAU`, which #3245 renames

## EPFL deployment (ops repository)

The ops repository changes first, and this branch lands after it. The new
image stops without the nine required values and the assets volume. The
image of today ignores a value that it does not know, so the new values are
safe to add early. The three old `APP_ACCESS_MANAGEMENT_PROVIDER_*` values
stay until the new image runs, then a second change deletes them.

Before the next deployment, a human changes the ops repository:

- Rename `APP_ACCESS_MANAGEMENT_PROVIDER_URL` to
  `APP_ACCESS_MANAGEMENT_URL`.
- Rename `APP_ACCESS_MANAGEMENT_PROVIDER_ABOUT_URL` to
  `APP_ACCESS_MANAGEMENT_ABOUT_URL`.
- Delete `APP_ACCESS_MANAGEMENT_PROVIDER_NAME`.
- Keep the EPFL folder at `epfl/co2-calculator/base/institution/`: the
  logo, the icons, the login illustration and `theme.conf`. The folder
  can also hold a `values.env` with the institution values.
- Keep the per-cluster values (`APP_ENVIRONMENT`, `APP_SENTRY_DSN`,
  `APP_MATOMO_*`, `APP_OPS_*`) in the overlays, under `frontend.env`.
- Set `APP_MATOMO_URL` and `APP_PRODUCTION_URL` where they are used.
- Give the volume as a ConfigMap made from that folder with
  `binaryData`. The folder has no font files: its `theme.conf` points the
  fonts at the ENAC font server. Without font keys, the ConfigMap needs no
  `items` list.
- Set `FRONTEND_URL` and `DB_URL` for the backend. They have no default.

A developer also adds `FRONTEND_URL` to `backend/.env`. To see EPFL
locally, a developer sets `INSTITUTION_DIR` to the EPFL folder.

## Caveats

- The first-load badge counts only the bundle. The fonts of the
  deployment are not known at build time.
- Without the font preloads, the browser finds the fonts later, when it
  applies `theme.css`: about 155 ms after the page request, against 36 ms
  with the preloads (login page, local build, real font server). The first
  text can show the fallback font a little longer. The first paint does not
  wait for the fonts, and Lighthouse gives it 1.50 s against 1.96 s before.
- The logo is now a file of the deployment, not a part of the bundle, so
  the browser asks for it only when the app starts. The logo of the login
  page loads eagerly and without a fade, and it paints with the first text
  (149 ms against 148 ms before this change, 294 ms without these settings).
  The mobile simulation of Lighthouse still counts the logo as the largest
  paint and gives 4.2 s against 1.96 s, score 86 against 98. With the
  desktop preset of the nightly job, the score is 99 against 100 (0.94 s
  against 0.49 s). Three other changes did not move the mobile number, so
  the branch has none of them: a preload of the logo, a high fetch priority,
  and the logo in the static page.
- The `institution-words` job is a required check only after an admin adds
  it to the branch protection of `dev` and `main`.
- A change of `theme.conf` or of `values.env` reloads the dev server
  page. A change of `.env.local` needs a restart of the dev server.
- The check of secret names reads the key, not the value. It stops a key
  such as `APP_API_TOKEN`. It cannot see a secret under a neutral name.

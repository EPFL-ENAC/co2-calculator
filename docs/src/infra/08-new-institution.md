# Set up a new institution

Another institution runs the same images as EPFL. It changes no code. It
gives the frontend a values file and a folder of assets. This page shows
how. The example institution is `UNIV`, in the folder `institutions/univ`.

This page covers what #3244 delivers. The frontend is fully configurable.
Login and units still need Accred and Entra, or the test login. See
[Limits today](#limits-today). The design and the full list of values are
in the [plan of #3244](../implementation-plans/3244-institution-values-assets-theme.md).

## 1. Copy the EPFL folder

1. Copy the EPFL folder to a folder for the new institution.
2. Make the values file from its example.

```sh
cp -R institutions/epfl institutions/univ
mv institutions/univ/frontend.env.example institutions/univ/frontend.env
```

Git ignores `institutions/*/frontend.env`, but it does not ignore the
assets folder. The CI word check allows EPFL words only in
`institutions/epfl/`. So `make lint` fails while an EPFL value is still
in the new folder. When `make lint` passes, you replaced every EPFL
value.

The folder can also live outside this repository, for example in the ops
repository of the institution. The two paths in step 5 and the volume in
step 7 then point there.

## 2. Set the values

Put the values of the institution in `institutions/univ/frontend.env`.

```sh
# Required.
APP_INSTITUTION_NAME=UNIV
APP_INSTITUTION_NAME_FR_DE=de l'UNIV
APP_INSTITUTION_NAME_FR_A=à l'UNIV
APP_INSTITUTIONAL_ID_LABEL=Person ID
APP_CONTACT_EMAIL=co2-support@example.org
APP_USER_DOC_URL=https://docs.example.org/co2-user/
APP_BACKOFFICE_DOC_URL=https://docs.example.org/co2-backoffice/
APP_STRATEGY_URL_EN=https://www.example.org/climate-strategy/
APP_STRATEGY_URL_FR=https://www.example.org/fr/strategie-climat/

# Optional. An empty value hides the link.
APP_ACCESS_MANAGEMENT_URL=
APP_ACCESS_MANAGEMENT_ABOUT_URL=
APP_ROLES_DOC_URL=
APP_SOURCE_CODE_URL=
APP_USER_DOC_SOURCE_URL=
APP_BACKOFFICE_DOC_SOURCE_URL=
APP_DEVELOPER_DOC_URL=
APP_PLANNER_MIN_YEAR=2016
APP_PLANNER_MAX_YEAR=2050
```

| Value                                        | Content                                                  |
| -------------------------------------------- | -------------------------------------------------------- |
| `APP_INSTITUTION_NAME`                       | the short name, as the texts show it                     |
| `APP_INSTITUTION_NAME_FR_DE`                 | the French "of" form, for example `de l'UNIV`            |
| `APP_INSTITUTION_NAME_FR_A`                  | the French "at" form, for example `à l'UNIV`             |
| `APP_INSTITUTIONAL_ID_LABEL`                 | the word for the person ID, for example `SCIPER` at EPFL |
| `APP_CONTACT_EMAIL`                          | the support address of the calculator                    |
| `APP_USER_DOC_URL`                           | the user documentation, with a `/` at the end            |
| `APP_BACKOFFICE_DOC_URL`                     | the back-office documentation, with a `/` at the end     |
| `APP_STRATEGY_URL_EN`, `APP_STRATEGY_URL_FR` | the English and French pages of the climate strategy     |

The texts insert the French forms as they are. For example, the French
tab title is "Calculateur CO₂ de l'UNIV". The texts add page paths after
the two doc URLs, so each URL must end with `/`. The ID label replaces
"SCIPER" in the texts and in the headcount column.

The values that change per cluster do not go in this file:
`APP_ENVIRONMENT`, `APP_SENTRY_DSN`, `APP_MATOMO_*`, `APP_OPS_*`,
`APP_DEMO_MODE` and `APP_PRODUCTION_URL`. If you set `APP_MATOMO_SITE_ID`,
you must also set `APP_MATOMO_URL`. If `APP_DEMO_MODE` is `true`, you
must also set `APP_PRODUCTION_URL`.

## 3. Replace the assets

Replace the files in `institutions/univ/assets/`. Every file must exist
and must not be empty, or the container stops.

| File                                         | Content                                        |
| -------------------------------------------- | ---------------------------------------------- |
| `logo.svg`                                   | the logo of the institution                    |
| `login-illustration.svg`                     | the image of the login page                    |
| `favicon.ico`                                | the browser icon                               |
| `favicon-16x16.png` to `favicon-128x128.png` | the browser icons in 16, 32, 96 and 128 pixels |
| `fonts/regular.woff2`                        | the text font, weight 400                      |
| `fonts/medium.woff2`                         | the text font, weight 500                      |
| `fonts/bold.woff2`                           | the text font, weight 700                      |
| `theme.conf`                                 | the colors and the corner radii                |

The repository is public. Before you commit the logo of an institution,
get the agreement of that institution.

The login page repeats `login-illustration.svg` as a tile behind the login
card, and it shows the file as it is. To make the illustration pale, put the
opacity in the file. The EPFL file draws its icons at 25 % opacity on a white
tile.

### Fonts and licensing

For a test, keep the Geist fonts of the EPFL folder. Their license
allows redistribution.

If the institution has a brand font, read its license before you add it
to any repository. A brand font license usually does not allow
redistribution. In that case, the cluster of the institution mounts the
font files, as the EPFL clusters do for Suisse Int'l. A system font such
as Arial is not allowed either. `institutions/epfl/assets/fonts/README.md`
gives the rules.

## 4. Set the colors

Set the accent color in `institutions/univ/assets/theme.conf`.

```
accent: #0050a0
```

Delete the `accent-hover`, `accent-light` and `accent-lighter` lines.
They hold the EPFL reds. Without them, the app mixes the three shades
from the accent.

The other names keep the default look. To change one, remove the `# `
in front of its line and set the value. Only `accent` is required.
`frontend/docker/theme.awk` lists all the names.

## 5. Run it locally

### With the dev server

1. Set these two lines in `frontend/.env.local`.
2. Restart the frontend dev server.

```sh
INSTITUTION_ENV_FILE=../institutions/univ/frontend.env
INSTITUTION_ASSETS_DIR=../institutions/univ/assets
```

### With the real container

1. In `docker-compose.yml`, find the frontend service.
2. Change `institutions/epfl` to `institutions/univ` in the `env_file`
   line and in the `volumes` line. Do not commit this change.
3. Run `docker compose up --build frontend`.

If the check passes, the log shows this line:

```
[institution] checked /institution and wrote /tmp/theme.css
```

## 6. Make sure that it works

Open the app and make sure of these points:

- The tab title is "UNIV CO₂ Calculator" in English and "Calculateur
  CO₂ de l'UNIV" in French.
- The login page shows the logo and the image of the institution.
- The accent buttons have the accent color.
- The home page names the institution and links to its strategy page.
- The headcount column header shows the ID label.
- With empty access values, the access popover shows no link.

Then test the failures:

| Change                            | Result                                                                                  |
| --------------------------------- | --------------------------------------------------------------------------------------- |
| Empty `APP_CONTACT_EMAIL`         | The app shows the missing-values page with `APP_CONTACT_EMAIL`.                         |
| Delete `fonts/bold.woff2`         | The container stops: `[institution] missing or empty in /institution: fonts/bold.woff2` |
| Add `colour: red` to `theme.conf` | The startup stops with the line number and `unknown name "colour"`.                     |

The dev server runs the same scripts, so it shows the same messages.

## 7. Deploy to a cluster

1. Set the values under `frontend.env` in the Helm values of the
   cluster.
2. Make a ConfigMap from the assets folder.
3. Mount the ConfigMap with `frontend.institutionAssets.volume`.

Without the volume, the Helm chart does not render.

A ConfigMap key cannot contain `/`. So give each font its own key:

```sh
kubectl create configmap co2-institution \
  --from-file=institutions/univ/assets \
  --from-file=fonts-regular.woff2=institutions/univ/assets/fonts/regular.woff2 \
  --from-file=fonts-medium.woff2=institutions/univ/assets/fonts/medium.woff2 \
  --from-file=fonts-bold.woff2=institutions/univ/assets/fonts/bold.woff2
```

Then map the font keys back to `fonts/`. List every file in `items`,
because Kubernetes mounts only the keys that `items` lists.

```yaml
frontend:
  institutionAssets:
    volume:
      configMap:
        name: co2-institution
        items:
          - { key: logo.svg, path: logo.svg }
          - { key: login-illustration.svg, path: login-illustration.svg }
          - { key: favicon.ico, path: favicon.ico }
          - { key: favicon-16x16.png, path: favicon-16x16.png }
          - { key: favicon-32x32.png, path: favicon-32x32.png }
          - { key: favicon-96x96.png, path: favicon-96x96.png }
          - { key: favicon-128x128.png, path: favicon-128x128.png }
          - { key: theme.conf, path: theme.conf }
          - { key: fonts-regular.woff2, path: fonts/regular.woff2 }
          - { key: fonts-medium.woff2, path: fonts/medium.woff2 }
          - { key: fonts-bold.woff2, path: fonts/bold.woff2 }
```

The backend also needs `DB_URL` and `FRONTEND_URL`. They have no default.

## Limits today

A new institution can change everything that people see. It cannot use
its own login yet, except the test login. The other parts of #500
remove the remaining EPFL dependencies:

| Issue | Delivers                                                                        |
| ----- | ------------------------------------------------------------------------------- |
| #3245 | switches for monitoring, error reports, audit export and Tableau                |
| #3246 | login and units without Accred                                                  |
| #3248 | unit levels, SIUS codes and exchange rates                                      |
| #3250 | local Keycloak login, the full app in Docker Compose, the full deployment guide |

When #3250 ships, update this page with the login and units steps.

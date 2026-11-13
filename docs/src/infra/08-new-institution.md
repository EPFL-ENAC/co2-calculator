# Set up a new institution

Another institution runs the same images as EPFL. It changes no code. It
gives the frontend a values file and a folder of assets. The image has a
neutral default for every asset except the theme, so the smallest folder
holds only `theme.conf` with the accent color. This page shows how. The example institution is `UNIV`, in the folder `institutions/univ`.

This page covers what #3244 delivers. The frontend is fully configurable.
Login and units still need Accred and Entra, or the test login. See
[Limits today](#limits-today). The design and the full list of values are
in the [plan of #3244](../implementation-plans/3244-institution-values-assets-theme.md).

## 1. Make the folder

1. Make a folder for the new institution.
2. Copy the values file of EPFL into it.
3. Copy the theme template into its assets folder.

```sh
mkdir -p institutions/univ/assets
cp institutions/epfl/frontend.env.example institutions/univ/frontend.env
cp frontend/institution-default/theme.conf.example institutions/univ/assets/theme.conf
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
the two doc URLs, so each URL must end with `/`. If one does not, the app
shows the missing-values page with that URL. The ID label replaces
"SCIPER" in the texts and in the headcount column.

The values that change per cluster do not go in this file:
`APP_ENVIRONMENT`, `APP_SENTRY_DSN`, `APP_MATOMO_*`, `APP_OPS_*`,
`APP_DEMO_MODE` and `APP_PRODUCTION_URL`. If you set `APP_MATOMO_SITE_ID`,
you must also set `APP_MATOMO_URL`. If `APP_DEMO_MODE` is `true`, you
must also set `APP_PRODUCTION_URL`.

## 3. Replace the assets you want

The image has a neutral default for each file below:
a gray logo and icons, a gray login illustration and the Geist fonts.
`frontend/institution-default/` holds them. To replace a default, put a
file with the same name in `institutions/univ/assets/`. Every other file
keeps its default.

| File                                         | Content                                        |
| -------------------------------------------- | ---------------------------------------------- |
| `logo.svg`                                   | the logo of the institution                    |
| `login-illustration.svg`                     | the image of the login page                    |
| `favicon.ico`                                | the browser icon                               |
| `favicon-16x16.png` to `favicon-128x128.png` | the browser icons in 16, 32, 96 and 128 pixels |
| `fonts/regular.woff2`                        | the text font, weight 400                      |
| `fonts/medium.woff2`                         | the text font, weight 500                      |
| `fonts/bold.woff2`                           | the text font, weight 700                      |

If the folder holds a file name that is not in this table or
`theme.conf`, the container stops. This catches a typo, for example
`logo.SVG`, that would show the default logo without an error. One
exception: `fonts/` can also hold a file that is not a `.woff2`, for
example the license of a free font. An empty file also stops the
container. At startup, the log gives the source of each
file:

```
[institution] logo.svg: from /institution
[institution] favicon.ico: from /usr/local/share/institution/default
```

The repository is public. Before you commit the logo of an institution,
get the agreement of that institution.

The login page repeats `login-illustration.svg` as a tile behind the login
card, and it shows the file as it is. To make the illustration pale, put the
opacity in the file. The default file draws its icons at 25 % opacity on a
white tile.

### Fonts and licensing

If the institution has a brand font, read its license before you add it
to any repository. A brand font license usually does not allow
redistribution. In that case, do not add the files. Set the URLs of the
font server of the institution in `theme.conf`, as EPFL does:

```
font-regular: https://fonts.example.org/Brand-Regular.woff2
font-medium: https://fonts.example.org/Brand-Medium.woff2
font-bold: https://fonts.example.org/Brand-Bold.woff2
```

The font server must allow the site of the calculator in its CORS headers.
A system font such as Arial is not allowed in the folder either.
`frontend/institution-default/fonts/README.md` gives the rules.

## 4. Set the colors

Set the accent color in `institutions/univ/assets/theme.conf`. The
template sets a neutral gray.

```
accent: #0050a0
```

The app mixes the hover and light shades from the accent. The other names
keep the default look. To change one, remove the `# ` in front of its
line and set the value. Only `accent` is required.
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
[institution] wrote /tmp/institution and /tmp/theme.css
```

## 6. Make sure that it works

Open the app and make sure of these points:

- The tab title is "UNIV CO₂ Calculator" in English and "Calculateur
  CO₂ de l'UNIV" in French.
- The login page shows the logo and the image of the institution, or the
  gray defaults for the files that you did not give.
- The accent buttons have the accent color.
- The home page names the institution and links to its strategy page.
- The headcount column header shows the ID label.
- With empty access values, the access popover shows no link.

Then test the failures:

| Change                            | Result                                                                         |
| --------------------------------- | ------------------------------------------------------------------------------ |
| Empty `APP_CONTACT_EMAIL`         | The app shows the missing-values page with `APP_CONTACT_EMAIL`.                |
| Delete `theme.conf`               | The container stops: `[institution] missing or empty: /institution/theme.conf` |
| Rename `logo.svg` to `logo.SVG`   | The container stops: `[institution] unknown files in /institution: logo.SVG`   |
| Add `colour: red` to `theme.conf` | The startup stops with the line number and `unknown name "colour"`.            |

The dev server runs the same scripts, so it shows the same messages.

## 7. Deploy to a cluster

1. Set the values under `frontend.env` in the Helm values of the
   cluster.
2. Make a ConfigMap from the assets folder.
3. Mount the ConfigMap with `frontend.institutionAssets.volume`.

Without the volume, the Helm chart does not render, because the volume
gives `theme.conf`.

Put only the files that replace a default in the ConfigMap. The smallest
ConfigMap holds `theme.conf` alone:

```sh
kubectl create configmap co2-institution \
  --from-file=institutions/univ/assets/theme.conf
```

```yaml
frontend:
  institutionAssets:
    volume:
      configMap:
        name: co2-institution
```

Without `items`, Kubernetes mounts every key of the ConfigMap. A key
cannot contain `/`, so a font file needs its own key and an `items` entry
that maps it to `fonts/`, for example
`{ key: fonts-bold.woff2, path: fonts/bold.woff2 }`. With `items`, list
every file, because Kubernetes then mounts only the keys that `items`
lists. To avoid this, point `theme.conf` at a font server.

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

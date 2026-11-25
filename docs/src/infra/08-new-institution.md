# Set up a new institution

Another institution runs the same images as EPFL. It changes no code. It
gives the frontend one folder: `values.env`, `theme.conf` and optional
assets. The image has a neutral default for every asset except the theme,
so the smallest folder holds only `theme.conf` with the accent color.
This page shows how. The example institution is `UNIV`, in the folder
`../co2-institution-univ/`, next to the app repository.

This page covers what #3244 delivers. The frontend is fully configurable.
Login and units still need Accred and Entra, or the test login. See
[Limits today](#limits-today). The design and the full list of values are
in the [plan of #3244](../implementation-plans/3244-institution-values-assets-theme.md).

## One folder for each institution

An institution can publish its folder as a small repository of its own.
The three consumers take the same folder:

- the dev server, through `INSTITUTION_DIR` in `frontend/.env.local`
- Docker Compose, through a volume at `/institution`
- a cluster, through a ConfigMap mounted at `/institution`

EPFL does this. The repository
[co2-institution-epfl](https://github.com/EPFL-ENAC/co2-institution-epfl)
holds the folder and a small Helm chart that makes the ConfigMap. Use it
as a model for a new institution.

## 1. Make the folder

1. Make the folder outside the app repository.
2. Copy the values of the example institution into it.
3. Copy the theme template into it.

```sh
mkdir ../co2-institution-univ
cp frontend/institution-example/values.env ../co2-institution-univ/values.env
cp frontend/institution-default/theme.conf.example ../co2-institution-univ/theme.conf
```

The app repository names no institution. Keep the folder in the ops
repository of the institution, or in a repository of its own.

## 2. Set the values

Put the values of the institution in `values.env` of the folder.

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
APP_PLANNER_MIN_YEAR=2016
APP_PLANNER_MAX_YEAR=2050

# Optional. An empty value hides the link.
APP_ACCESS_MANAGEMENT_URL=
APP_ACCESS_MANAGEMENT_ABOUT_URL=
APP_ROLES_DOC_URL=
APP_SOURCE_CODE_URL=
APP_USER_DOC_SOURCE_URL=
APP_BACKOFFICE_DOC_SOURCE_URL=
APP_DEVELOPER_DOC_URL=
```

| Value                                          | Content                                                  |
| ---------------------------------------------- | -------------------------------------------------------- |
| `APP_INSTITUTION_NAME`                         | the short name, as the texts show it                     |
| `APP_INSTITUTION_NAME_FR_DE`                   | the French "of" form, for example `de l'UNIV`            |
| `APP_INSTITUTION_NAME_FR_A`                    | the French "at" form, for example `à l'UNIV`             |
| `APP_INSTITUTIONAL_ID_LABEL`                   | the word for the person ID, for example `SCIPER` at EPFL |
| `APP_CONTACT_EMAIL`                            | the support address of the calculator                    |
| `APP_USER_DOC_URL`                             | the user documentation, with a `/` at the end            |
| `APP_BACKOFFICE_DOC_URL`                       | the back-office documentation, with a `/` at the end     |
| `APP_STRATEGY_URL_EN`, `APP_STRATEGY_URL_FR`   | the English and French pages of the climate strategy     |
| `APP_PLANNER_MIN_YEAR`, `APP_PLANNER_MAX_YEAR` | the first and the last year of the project planner       |

The texts insert the French forms as they are. For example, the French
tab title is "Calculateur CO₂ de l'UNIV". The texts add page paths after
the two doc URLs, so each URL must end with `/`. If one does not, the
frontend stops at startup and the log names that URL. The French
header link adds `fr/` after `APP_USER_DOC_URL`, so the user
documentation must have its French pages under `fr/`. The ID label
replaces "SCIPER" in the texts and in the headcount column.

Every `APP_*` value is public. The frontend sends them to each browser,
without a login. Do not put a password, a token or a key in an `APP_*`
value. The frontend sends only the names of this page. An other name in
`values.env` stops the frontend at startup. An other `APP_*` variable of
the environment is logged and not sent. Each `*_URL` value must start
with `http://` or `https://`.

The container reads `/institution/values.env`, then the environment of
the pod. A variable of the environment, empty or not, wins over the file. The Helm chart does not send an empty `frontend.env` value to
the pod, so the value of the file stays. `APP_ENVIRONMENT` is required in the environment: the Helm chart
gives `production`. `APP_ENVIRONMENT` and
`APP_DEMO_MODE` in `values.env` stop the frontend, because the chart gives
them a value. Put the values
that change per cluster in the environment: `APP_ENVIRONMENT`,
`APP_SENTRY_DSN`, `APP_MATOMO_*`, `APP_OPS_*`, `APP_DEMO_MODE` and
`APP_PRODUCTION_URL`. If you set `APP_MATOMO_SITE_ID`,
you must also set `APP_MATOMO_URL`. If `APP_DEMO_MODE` is `true`, you
must also set `APP_PRODUCTION_URL`.

## 3. Replace the assets you want

The image has a neutral default for each file below:
a gray logo and icons, a gray login illustration and the Geist fonts.
`frontend/institution-default/` holds them. To replace a default, put a
file with the same name in the folder. Every other file
keeps its default.

| File                                         | Content                                        |
| -------------------------------------------- | ---------------------------------------------- |
| `logo.svg`                                   | the logo of the institution                    |
| `login-illustration.svg`                     | the image of the login page                    |
| `favicon.ico`                                | the browser icon                               |
| `favicon-16x16.png` to `favicon-128x128.png` | the browser icons in 16, 32, 96 and 128 pixels |
| `font-regular.woff2`                         | the text font, weight 400                      |
| `font-medium.woff2`                          | the text font, weight 500                      |
| `font-bold.woff2`                            | the text font, weight 700                      |
| `offnet.html`                                | the page for clients outside the networks      |

The folder is flat. A subfolder stops the container.
If the folder holds a file name that is not in this table or
`theme.conf`, the container stops. Without this stop, a typo such as `logo.SVG`
shows the default logo and no error. One
exception: a file whose name starts with `font-` and does not end with
`.woff2` is allowed, for example `font-license.txt`. Use it for the
license of a free font. The container does not serve this file. An
empty file also stops the container. At startup, the log gives the source of each
file:

```
[entrypoint] logo.svg: from /institution
[entrypoint] favicon.ico: from /usr/local/share/institution/default
```

If the folder is in a public repository, get the agreement of the
institution before you commit its logo.

The login page repeats `login-illustration.svg` as a tile behind the login
card, and it shows the file as it is. To make the illustration pale, put the
opacity in the file. The default file draws its icons at 25 % opacity on a
white tile.

### The page for clients outside the networks

If the chart sets `clientAllowlist.allowedCidrs`, a client outside these
networks gets `offnet.html` and no other file. The default page has
neutral texts in English and French, with no name and no contact.

To replace it, write one self-contained `offnet.html`. Put the texts, the
CSS, the script, the logo and the icon in the file. Use inline SVG or
`data:` URLs for the images. A file of the calculator, for example
`/theme.css` or `/institution/logo.svg`, does not load for these clients.
A font can come from a font server on an other host.

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
`frontend/institution-default/font-README.md` gives the rules.

## 4. Set the colors

Set the accent color in `theme.conf` of the folder. The
template sets a neutral gray.

```
accent: #0050a0
```

The app mixes the hover and light shades from the accent. The other names
keep the default look. To change one, remove the `# ` in front of its
line and set the value. Only `accent` is required.
`frontend/docker/entrypoint.sh` lists all the names.

A color is a hex value, for example `#0050a0`. A radius is a number with
`px`, `rem`, `em` or `%`. Any other value stops the frontend at startup.

## 5. Run it locally

### With the dev server

1. Set this line in `frontend/.env.local`. The path is relative to
   `frontend/`.
2. Restart the frontend dev server.

```sh
INSTITUTION_DIR=../../co2-institution-univ
```

After that, a change of a file in the folder reloads the page. You do
not restart the dev server again. Without `INSTITUTION_DIR`, the dev
server uses `frontend/institution-example/`.

### With the real container

1. In `docker-compose.yml`, find the frontend service.
2. In the `volumes` line, change `./frontend/institution-example` to
   `../co2-institution-univ`. Do not commit this change.
3. Run `docker compose up --build frontend`.

If the check passes, the log shows this line:

```
[entrypoint] wrote injectEnv.js, institution/ and theme.css in /tmp
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

| Change                            | Result                                                                        |
| --------------------------------- | ----------------------------------------------------------------------------- |
| Empty `APP_CONTACT_EMAIL`         | The container stops: `[entrypoint] APP_CONTACT_EMAIL is required and empty`   |
| Delete `theme.conf`               | The container stops: `[entrypoint] missing or empty: /institution/theme.conf` |
| Rename `logo.svg` to `logo.SVG`   | The container stops: `[entrypoint] unknown files in /institution: logo.SVG`   |
| Add `colour: red` to `theme.conf` | The startup stops with the line number and `unknown name "colour"`.           |
| Set `accent: red` in `theme.conf` | The startup stops with the line number and `"accent" must be a hex color`.    |

The dev server runs the same script, so it shows the same messages.

## 7. Make the institution image

An image carries the folder to a cluster and to Docker Compose, with a
version. The host needs no clone of your repository. The folder is at
`/institution` in the image. The command of the image copies it into the
volume at `/out`, for the init container of the Helm chart.

Put this `Dockerfile` next to the folder, named `institution/` here:

```dockerfile
FROM busybox:1.37-musl
COPY institution/ /institution/
USER 65534
CMD ["sh", "-c", "rm -rf /out/* && cp -R /institution/. /out/"]
```

Build the image and push it to your registry, with a version tag:

```sh
docker build -t registry.example.org/co2-institution-univ:v1.0.0 .
docker push registry.example.org/co2-institution-univ:v1.0.0
```

The EPFL repository shows a CI job that builds and publishes the image
for each version tag.

## 8. Deploy

### On a cluster

1. Set `frontend.institutionAssets.image` to the image, with its tag.
2. Set the per-cluster values under `frontend.env` in the Helm values.

```yaml
frontend:
  institutionAssets:
    image: registry.example.org/co2-institution-univ:v1.0.0
```

An init container runs the image before the frontend starts. A new tag
changes the pod template, so the cluster restarts the frontend pods.

You can also set the institution values under `frontend.env` instead of
`values.env`. A variable of the environment wins over the file.

Without `image` or `volume`, the Helm chart does not render, because the
folder gives `theme.conf`. With an empty required value, the new pods
stop at startup and the pods of the last version continue to serve.

### With Docker Compose

`docker-compose.deploy.yml` starts the app from published images. Set
`INSTITUTION_IMAGE` to the image, with its tag. The frontend mounts the
folder of the image directly, read-only. The
[install page](install.md) gives the steps.

### From a volume

`frontend.institutionAssets.volume` takes any volume source in place of
the image, for example a ConfigMap. The frontend reads the folder only at
startup, and a change of a ConfigMap does not restart a pod. Change
something in the pod template each time you change the folder.

Put only the files that replace a default in the ConfigMap. The smallest
ConfigMap holds `theme.conf` alone:

```sh
kubectl create configmap co2-institution \
  --from-file=../co2-institution-univ/theme.conf
```

```yaml
frontend:
  institutionAssets:
    volume:
      configMap:
        name: co2-institution
```

The folder is flat, so a ConfigMap of the folder needs no `items`
mapping. A ConfigMap is limited to 1 MiB. For a large font set, use a
font server and put its URLs in `theme.conf`.

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

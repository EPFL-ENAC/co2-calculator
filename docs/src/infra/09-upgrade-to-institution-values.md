# Upgrade to institution values

Issue #3244 removes each EPFL default from the code. The institution
values now come from the deployment. This page lists the variables that
you must add, rename or delete for this version, in a developer checkout
and in a cluster. The design is in the
[plan of #3244](../implementation-plans/3244-institution-values-assets-theme.md).

> CAUTION: Change the ops repository before you deploy this version.
> If a required value is empty, the new frontend container stops at
> startup. If `FRONTEND_URL` is empty, the new backend stops.

## Backend variables

No backend variable has a new name. Two variables lose their default.
If one of them is empty, the backend stops at boot.

| Variable       | Before                           | Now      |
| -------------- | -------------------------------- | -------- |
| `DB_URL`       | default: a local SQLite file     | required |
| `FRONTEND_URL` | default: `http://localhost:9000` | required |

If your `backend/.env` is older than this version, make sure that it
sets the two variables. Compare it with `backend/.env.example`.

The `GET /v1/unit/{unit_id}/results` endpoint is removed. It returned a
fixed EPFL answer and the app did not call it.

## Frontend variables

Nine variables are new and required. If one of them is empty, the
container stops.

```sh
APP_INSTITUTION_NAME=
APP_INSTITUTION_NAME_FR_DE=
APP_INSTITUTION_NAME_FR_A=
APP_INSTITUTIONAL_ID_LABEL=
APP_CONTACT_EMAIL=
APP_USER_DOC_URL=          # must end with /
APP_BACKOFFICE_DOC_URL=    # must end with /
APP_STRATEGY_URL_EN=
APP_STRATEGY_URL_FR=
```

Three variables have a new name or are deleted.

| Before                                     | Now                               |
| ------------------------------------------ | --------------------------------- |
| `APP_ACCESS_MANAGEMENT_PROVIDER_URL`       | `APP_ACCESS_MANAGEMENT_URL`       |
| `APP_ACCESS_MANAGEMENT_PROVIDER_ABOUT_URL` | `APP_ACCESS_MANAGEMENT_ABOUT_URL` |
| `APP_ACCESS_MANAGEMENT_PROVIDER_NAME`      | deleted                           |

These variables are new and optional. An empty value hides the link.

- `APP_SOURCE_CODE_URL`, `APP_USER_DOC_SOURCE_URL`,
  `APP_BACKOFFICE_DOC_SOURCE_URL`, `APP_DEVELOPER_DOC_URL`
- `APP_OPS_ARGOCD_URL`, `APP_OPS_GRAFANA_DASHBOARD_URL`,
  `APP_OPS_GRAFANA_GRAPHS_URL`, `APP_OPS_LOGS_URL`,
  `APP_OPS_OPENSHIFT_URL`

Three variables lose their EPFL default.

| Variable                             | Now                                  |
| ------------------------------------ | ------------------------------------ |
| `APP_MATOMO_URL`                     | required with `APP_MATOMO_SITE_ID`   |
| `APP_PRODUCTION_URL`                 | required with `APP_DEMO_MODE=true`   |
| `APP_EQUIPMENT_POWER_FEEDBACK_EMAIL` | an empty value hides the request tab |

Each `APP_*` value is public, because the frontend sends it to each
browser. A variable whose name contains `SECRET`, `PASSWORD`, `TOKEN`,
`CREDENTIAL` or `PRIVATE` stops the container.

## Update a developer checkout

1. Pull the branch.
2. Run `make install` at the repository root. It copies
   `institutions/epfl/frontend.env.example` to
   `institutions/epfl/frontend.env`.
3. Add these two lines to `frontend/.env.local`.
4. Delete each `APP_ACCESS_MANAGEMENT_PROVIDER_*` line from
   `frontend/.env.local`.
5. Start the frontend dev server again.

```sh
INSTITUTION_ENV_FILE=../institutions/epfl/frontend.env
INSTITUTION_ASSETS_DIR=../institutions/epfl/assets
```

Node reads `frontend/.env.local` now. If a value contains `#`, put the
value in quotes.

If you seed the reduction objectives, rename the local input file in
`backend/INPUT_DATA/` from `reduction_obj_epfl_footprint(in).csv` to
`reduction_obj_institution_footprint(in).csv`.

Docker Compose reads `DB_URL` from `backend/.env` and changes the host
`localhost` to `postgres`. It refuses each other host.

## Update a cluster

1. Add the nine required variables under `frontend.env`.
2. Rename the two access management variables and delete the third.
3. Set `APP_MATOMO_URL` and `APP_PRODUCTION_URL` where you use them.
4. Make a ConfigMap from the assets folder of the institution. The
   folder must contain `theme.conf`.
5. Set `frontend.institutionAssets.volume` to that ConfigMap. Without
   it, the Helm chart does not render.
6. Set `FRONTEND_URL` and `DB_URL` for the backend.

The old frontend image ignores a variable that it does not know. Thus
you can add the new variables before you deploy the new image.
[Set up a new institution](./08-new-institution.md) gives the content of
each value and of the assets folder.

## Make sure that the upgrade is correct

Start the frontend and read its log. This line shows a correct start:

```
[entrypoint] wrote injectEnv.js, institution/ and theme.css in /tmp
```

If a value is wrong, the log names it, for example
`[entrypoint] APP_CONTACT_EMAIL is required and empty`. Correct the
value and start the container again.

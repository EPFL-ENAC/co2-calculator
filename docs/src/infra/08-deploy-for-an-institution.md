# Deploy for Another Institution

This page tells an institution how to run the CO2 calculator with its own
name, look, identity provider and units. It changes no code: the same
images run everywhere, and the deployment sets the differences. The values
are in the [configuration reference](09-institution-configuration.md).

The app has no hidden default for an institution value. A missing required
value stops the startup and names the value, in the log of the backend or on
the page of the frontend. An optional service stays off until you turn it on.

## Before you start

You need these items:

- A Kubernetes cluster with Helm, or a machine with Docker Compose.
- A PostgreSQL database.
- An OpenID Connect identity provider, for example Keycloak or Microsoft
  Entra ID, with a confidential client for the app.
- The unit tree of the institution, as a CSV file.
- The logo, the favicon, the login illustration and the fonts.

## Steps

1. Copy `frontend/institution/epfl` to a new folder, for example
   `institution/my-university`. Replace each file with your own. Keep the
   file names: the container checks them at startup.
2. Edit `theme.env` in that folder. Set `colors-accent` to your accent color.
   Set the other tokens only where your colors differ from the base design.
3. Write the units CSV file. Each unit names its parent, and the root has
   level 1. Decide which level owns a workspace (its own carbon report) and
   which levels the back office reports on.
4. Name the roles in your identity provider. Each role reads
   `<role>@global`, `<role>@unit:<id>` or `<role>@affiliation:<id>`, for
   example `calco2.user.principal@unit:12345`. With Keycloak, create groups
   with these names and add a group membership mapper to the client.
5. Set the frontend variables. Start from `frontend/.env.example`.
6. Set the backend variables. Start from `backend/.env.example`.
7. Turn on the services you use: Tableau, Elasticsearch, OpenTelemetry,
   Loki, Matomo, GlitchTip. Leave the others off.
8. Deploy, then open the app. If it does not start, read the message: it
   names what is missing.

## With Helm

Put the values in the values file of your deployment, not in
`helm/values.yaml`.

- `frontend.env`: the `APP_*` variables of the frontend.
- `frontend.institutionAssets.volume`: a volume with your assets folder,
  for example a ConfigMap made from it. Put binary files in its
  `binaryData`.
- `backend.env`: the backend variables that are not secrets.
- `backend.units.csvConfigMap`: the name of a ConfigMap whose key
  `units.csv` holds your unit tree.
- `backend.tableau.modules`, `backend.elasticsearch.enabled`,
  `backend.observability`: the switches.

The secrets (`OAUTH_CLIENT_SECRET`, the HMAC keys, the encryption keys) go
in the existing secret of the chart. The worker uses the same backend values.

## With Docker Compose

The Keycloak overlay is a complete example of a deployment without EPFL
services. Read `docker-compose.keycloak.yml` and change its values:

```bash
make run-keycloak
```

It mounts the assets folder into the frontend container and the units file
into the backend container. The frontend reads its variables from
`frontend/.env.local`, the backend from `backend/.env`, and the overlay sets
the values that differ.

## Check the deployment

Log in with a test user of each role, then check these points:

- The header, the login page and the page title show your name and logo.
- The buttons and the links use your accent color.
- A new year in the back office creates the workspaces of your units.
- A principal user sees its unit and can delegate roles in your access
  portal.

For the local stack, `make test-keycloak` drives the login in a browser.

## Next step

Read the [configuration reference](09-institution-configuration.md) for each
variable, file and switch.

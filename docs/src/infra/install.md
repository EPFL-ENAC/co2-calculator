# Install the CO2 Calculator

This page shows the four ways to run the CO2 Calculator outside the
development setup. Use it to choose one, and to know what you must
supply before you start. It is the first part of the deployment guide
of issue #3250.

| Way            | Use it to                             | Login      |
| -------------- | ------------------------------------- | ---------- |
| Docker Compose | try the app on one machine            | test login |
| Skaffold       | try the Helm chart on a local cluster | test login |
| Helm chart     | run the app on Kubernetes             | OIDC       |
| Kustomize      | deploy with GitOps                    | OIDC       |

## Try it with Docker Compose

Docker Compose builds the images from the source and starts the app,
PostgreSQL and a web proxy on your machine. You need Docker and a clone
of the repository. The database starts empty.

> CAUTION: Do not put this setup on a network. Docker Compose sets
> `TEST_LOGIN_ROUTE_ENABLED=True`, and the test login then gives any role with no password.

1. Copy the example database file.
2. Start the app.
3. Open <http://localhost/en/login-test> and select a test role.

```bash
cp .database.env.example .database.env
docker compose up --build
```

The backend applies the database migrations at startup. Docker Compose
gives the backend the committed `backend/.env.example` and the
`postgres` service as its database. It does not read `backend/.env`,
which can name a shared database or real services for `make dev`.

## Try the chart on a local cluster with Skaffold

Skaffold builds the two images, and installs the chart on a cluster on
your machine. It also installs a local PostgreSQL, the two Secrets
with local values, and Traefik as the web proxy. When you change the
code, Skaffold builds and installs again.

> CAUTION: Use only a cluster on your machine. This setup sets
> `DEBUG=true`, and the test login then gives any role with no password.

1. Start a local cluster, for example Kubernetes in Docker Desktop.
2. Install Skaffold and Helm.
3. Start the loop. The command uses the context `docker-desktop`.
4. Open <http://localhost:8090/en/login-test> and select a test role.

```bash
make -C helm skaffold-dev
# For a different local cluster:
make -C helm skaffold-dev KUBE_CONTEXT=kind-co2
```

Use the host name `localhost`, not `127.0.0.1`. The backend sends the
login back to `http://localhost:8090`, and the browser keeps the session
cookie for that host only. The page `/en/login` needs an OIDC provider,
so it does not work in this setup. Use `/en/login-test`.

The database keeps its data in a persistent volume claim. To remove the
app and its data, run `make -C helm skaffold-delete`. Use the same
`KUBE_CONTEXT` as for `skaffold-dev`. The files of this setup are in
`helm/skaffold/`.

## Install on Kubernetes with Helm

The chart in `helm/` deploys the backend, the frontend and the
documentation site. It does not deploy PostgreSQL and it does not
create the Secrets. You supply these parts:

- a PostgreSQL database
- an OIDC login provider, for example Keycloak or Entra ID
- S3-compatible storage for uploaded files
- two Secrets, one for the database and one for the backend

The chart never creates a Secret. Create the two Secrets before you
install the chart, with `kubectl` or with a secret operator, for example
External Secrets or Sealed Secrets. If `backend.existingSecret.name` is
empty, the install stops.

The [chart README](https://github.com/epfl-enac/co2-calculator/blob/HEAD/helm/README.md) gives the steps.
[`helm/examples/`](https://github.com/epfl-enac/co2-calculator/blob/HEAD/helm/examples/values.yaml) holds a values file and
the two Secrets to copy. [`helm/VALUES.md`](https://github.com/epfl-enac/co2-calculator/blob/HEAD/helm/VALUES.md) lists each
value of the chart.

## Deploy with Kustomize and Argo CD

The chart is public at `oci://ghcr.io/epfl-enac/co2-calculator/helm`.
Kustomize can render it from a Git folder, and Argo CD can sync that
folder. The EPFL deployment works this way. The supplies are the same
as for the Helm chart.

1. Copy [`helm/examples/`](https://github.com/epfl-enac/co2-calculator/blob/HEAD/helm/examples/kustomization.yaml) to your
   Git repository.
2. Replace each `example.org` value in `values.yaml`.
3. Create the two Secrets of `secrets.yaml` with the secret tool of
   your cluster. Fill the six empty signing and encryption values.
4. Build the folder, or point an Argo CD application at it.

```bash
kustomize build --enable-helm helm/examples
```

> Note: With Helm 4, use Kustomize 5.8.1 or later. The Kustomize in
> `kubectl` 1.34 is older and fails with Helm 4.

## Limits today

The app still depends on EPFL services. These issues remove the limits.

| Issue | Limit today                                                  |
| ----- | ------------------------------------------------------------ |
| #3244 | The frontend shows the EPFL name, logo and colors.           |
| #3245 | The backend Secret needs the Elasticsearch keys.             |
| #3246 | Outside EPFL, a user logs in with no role and sees no units. |
| #3250 | Docker Compose has no real login, only the test login.       |

## Subsequent step

Start with Docker Compose to see the app. Then read the
[chart README](https://github.com/epfl-enac/co2-calculator/blob/HEAD/helm/README.md) and prepare the two Secrets. The Helm
chart and Kustomize use the same two Secrets. If a step
of this page fails, open an issue in the repository.

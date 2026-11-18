---
status: in-progress
issue: "3250"
last_updated: 2026-11-18
summary: First part of the deployment guide. A correct chart README, example values and Secrets that the lint renders, a generated values reference and an install page.
---

# 3250: install page and Helm example

## Problem

The Quick Start of the chart README did not install the chart. The command
`helm install co2-calc ./helm` stops, because the default values have no
name for the backend Secret. The README example made a backend Secret
with 2 keys, but the pods reference 26 keys and none is optional. The
real key list was only in the private ops repository.

`make lint` printed the same Secret-name message 31 times, because it
linted the chart with the default values.

## What this part delivers

- `helm/README.md` tells what the chart does not deploy and how to
  install it. It lists the limits.
- `helm/examples/values.yaml` and `helm/examples/secrets.yaml` are the
  public example of an installation.
- `helm/VALUES.md` is the values reference. `helm-docs` generates it
  from `values.yaml` with `make -C helm docs`.
- `helm/examples/kustomization.yaml` renders the published chart for a
  GitOps deployment.
- `helm/skaffold/` and `helm/skaffold.yaml` run the chart on a local
  cluster, with a local PostgreSQL, the two Secrets and Traefik. It ran
  on Docker Desktop: migrations, test login and `/api/v1/session`.
- `docs/src/infra/install.md` covers Docker Compose, Skaffold, the Helm
  chart and Kustomize. The home page links to it.

- `docker-compose.yml` runs the full app with the test login. The
  backend always uses the `postgres` service and `http://localhost`,
  whatever `backend/.env` holds. That file serves `make dev`, and its
  `DB_URL` can name a shared database. The frontend gets
  `APP_ENVIRONMENT=dev`, which adds the `/login-test` page. The
  PostgreSQL and Traefik health checks probe their own containers.

## Chart bugs that the local run found

- The default `API_VERSION` was `/api/v1`. FastAPI strips the root path
  `/api` before it routes, so each API call gave 404. Every EPFL overlay
  sets `/v1`, so no deployment saw the bug. The default is now `/v1`.
- The examples said that file encryption was optional. The startup check
  (#454) requires the file and credential encryption keys and salts, and
  `CONNECTOR_ALLOWED_HOST_SUFFIXES`. The examples now set them.

## Checks

`make -C helm lint` now runs four checks. The root `make lint` calls it,
and the new `helm-quality` job of `quality-check.yml` runs it on each
pull request. If `values.yaml` is staged, the pre-commit hook runs
`make -C helm docs`, as it does for the ERD.

| Target              | Fails when                                                |
| ------------------- | --------------------------------------------------------- |
| `lint-helm`         | the chart does not render with `examples/values.yaml`     |
| `lint-examples`     | an example Secret lacks a key that the pods read          |
| `check-api-version` | the backend does not render `API_VERSION=/v1`             |
| `lint-docs`         | `VALUES.md` is stale. Without `helm-docs`, it is skipped. |

Under `CI`, a missing `helm` or `helm-docs` fails the check. The
`helm-quality` job installs both, pinned and checked with SHA-256.

`examples/kustomization.yaml` pins chart 1.0.1797, built before this
PR. `examples/values.yaml` therefore sets `API_VERSION` and the three
exporters itself. When the example pins a newer chart, remove the four
lines.

## Not in this part

- Optional Secret keys for Accred, Elasticsearch and S3. See the comment
  on #3246.
- The chart-managed Secret (`backend.existingSecret.enabled=false`). It
  does not give a working deployment.
- Descriptions for each value. Only the values that an installation
  sets have a `# --` description.
- The full Docker Compose app with Keycloak, and the reference page.
  These stay in #3250.

## Follow-up for #3244

PR #3263 makes `frontend.institutionAssets.volume` and the institution
values required. After it merges, `lint-helm` fails until
`examples/values.yaml` sets them. That failure is the intent. The same
PR must do these two tasks:

- Run `make -C helm docs`, because the PR changes `values.yaml`.
- Update the Docker Compose steps of `docs/src/infra/install.md`,
  because the frontend container then needs an institution folder.

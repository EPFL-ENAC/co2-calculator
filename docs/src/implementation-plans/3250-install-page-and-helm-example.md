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
  backend reads the committed `backend/.env.example`, never
  `backend/.env`. That file serves `make dev`, and it can name a shared
  database, Elasticsearch or S3. Like the frontend, which sets each
  value inline, Compose reads no private file. The backend also gets the
  `postgres` service, `http://localhost` and an empty S3 host, so
  uploads stay in the container. The frontend gets
  `APP_ENVIRONMENT=development`, which adds the `/login-test` page and
  labels local errors apart from the deployed `dev`. The PostgreSQL and
  Traefik health checks probe their own containers.

## Chart bugs that the local run found

- The default `API_VERSION` was `/api/v1`. FastAPI strips the root path
  `/api` before it routes, so each API call gave 404. Every EPFL overlay
  sets `/v1`, so no deployment saw the bug. The default is now `/v1`.
- The examples said that file encryption was optional. The startup check
  (#454) requires the file and credential encryption keys and salts, and
  `CONNECTOR_ALLOWED_HOST_SUFFIXES`. The example values set the host
  list. The example Secret leaves the six signing and encryption values
  empty. The check refuses an empty value but accepts any other. With a
  placeholder such as `<change-me>`, the app runs with a public key.

## Checks

`make -C helm lint` now runs five checks. The root `make lint` calls it,
and the new `helm-quality` job of `quality-check.yml` runs it on each
pull request. If `values.yaml` is staged, the pre-commit hook runs
`make -C helm docs`, as it does for the ERD.

| Target              | Fails when                                                |
| ------------------- | --------------------------------------------------------- |
| `lint-helm`         | the chart does not render with `examples/values.yaml`     |
| `lint-examples`     | an example Secret lacks a key that the pods read          |
| `check-api-version` | the backend does not render `API_VERSION=/v1`             |
| `check-worker-env`  | the worker lacks `backend.env`, or a name repeats         |
| `lint-docs`         | `VALUES.md` is stale. Without `helm-docs`, it is skipped. |

Under `CI`, a missing `helm` or `helm-docs` fails the check. The
`helm-quality` job installs both, pinned and checked with SHA-256.

`examples/kustomization.yaml` pins chart 1.4.23 and images `v1.4.23`.
Since release 1.4.23, a release tag publishes the chart under the app
version, so the chart version and the image tag name the same release.

## Hardening after the review

- The chart has no chart-managed Secret. It made 5 of the 26 keys, so
  its pods did not start. `backend.existingSecret.name` is required.
- The database wait image is `postgres:18-alpine`, not an unpinned
  Bitnami image.
- The startup check refuses an encryption key or salt that is shorter
  than 32 characters or that starts with a placeholder. The live values
  are 65 characters.
- The worker gets `backend.env`, and `worker.env` overrides it. The
  worker does not get `RUN_PIPELINE_RECONCILER`, because the overlays
  turn it off on the API pods only. `check-worker-env` tests both.
- `make -C frontend audit` ignores GHSA-fc5q-39xc-vjpf (picomatch)
  until 2027-01-31. No fixed version exists, and the build tools
  require picomatch.

## Not in this part

- Optional Secret keys for Accred, Elasticsearch and S3. See the comment
  on #3246.
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

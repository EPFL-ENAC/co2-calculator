# CO2 Calculator Helm chart

This chart deploys the CO2 Calculator on Kubernetes: the backend, the
frontend, the documentation site and an optional worker for background
jobs. It does not deploy PostgreSQL and it does not create the Secrets.
This page tells you what you must supply and how to install the chart.

## Before you install

The chart needs these services. You supply each one.

- A Kubernetes cluster, version 1.24 or later, and Helm 3 or 4.
- A PostgreSQL database that the cluster can reach.
- A login provider that speaks OIDC, for example Keycloak or Entra ID.
- S3-compatible storage for uploaded files. The pods have no
  persistent volume.
- ingress-nginx, or OpenShift Routes (`routes.enabled`). The simple
  `ingress.hosts` form uses nginx regex paths and rewrites. For another
  controller, use the per-path form, as in
  [`skaffold/values-app.yaml`](skaffold/values-app.yaml).

## Create the two Secrets

The chart reads a database Secret and a backend Secret. It never
creates them: create them before you install the chart, with `kubectl`
or with a secret operator, for example External Secrets or Sealed
Secrets. If `backend.existingSecret.name` is empty, the install stops.
[`examples/secrets.yaml`](examples/secrets.yaml) lists each key and
tells you how to make each value.

> CAUTION: Do not remove a key from the backend Secret. The pods
> reference every key, and a pod with a missing key does not start.
> If a signing key, an encryption key or an encryption salt is empty,
> the backend stops at startup.

1. Copy `examples/secrets.yaml` to a location outside the repository.
2. Replace each `<change-me>` in the copy, and fill the six empty
   signing and encryption values.
3. Apply the copy to the namespace.

```bash
kubectl create namespace co2
kubectl apply --namespace co2 -f my-secrets.yaml
```

## Install the chart

1. Copy [`examples/values.yaml`](examples/values.yaml).
2. Replace each `example.org` value in the copy.
3. Set `backend.image.tag` and `frontend.image.tag` to one release tag,
   for example `v1.4.23`.
4. Install the chart from the root of the repository.

```bash
helm install co2 ./helm --namespace co2 -f my-values.yaml
kubectl get pods --namespace co2
```

A Job applies the database migrations at each install and each upgrade.
To upgrade, use `helm upgrade` with the same values file.

## Limits

- Outside EPFL, a user logs in with no role, and the app has no units.
  Issue #3246 removes this limit.
- If you do not use Accred or Elasticsearch, their keys must still
  exist in the backend Secret.

## Try it on a local cluster

`make -C helm skaffold-dev` installs the chart on a cluster on your
machine, with a local PostgreSQL, the two Secrets and Traefik. The
files are in [`skaffold/`](skaffold/values-app.yaml). The
[install page](../docs/src/infra/install.md) gives the steps.

## Kustomize

[`examples/kustomization.yaml`](examples/kustomization.yaml) renders
the published chart with the same values file. Use it for a GitOps
deployment, for example with Argo CD. It needs the same two Secrets.

## Values

[`VALUES.md`](VALUES.md) lists each value and its default. The tool
`helm-docs` generates this file from `values.yaml`. If the file is
stale and `helm-docs` is installed, `make -C helm lint` fails. After
you change `values.yaml`, run `make -C helm docs` and commit the two
files.

> Note: To change `values.yaml`, install `helm-docs` 1.14.2, the
> version that CI uses. The pre-commit hook needs it. Another version
> can give a different table. Get it with `brew install helm-docs` or
> from the
> [releases](https://github.com/norwoodj/helm-docs/releases/tag/v1.14.2).

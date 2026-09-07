# Infrastructure Overview

How co2-calculator is deployed on EPFL OpenShift and which parts live
where. Every statement here is backed by the private GitOps repository
(`openshift-app-config/epfl/co2-calculator`). When the two disagree, the
GitOps repo wins and this page needs a fix in the same PR. For what to do
when something breaks, go to [Operations](04-operations.md).

## Environments

| Env   | URL                            | Namespace                       | Cluster       | Git branch |
| ----- | ------------------------------ | ------------------------------- | ------------- | ---------- |
| dev   | `co2-calculator-dev.epfl.ch`   | `svc1751d-co2-calculator-dev`   | `ocpitsd0001` | `dev`      |
| stage | `co2-calculator-stage.epfl.ch` | `svc1751t-co2-calculator-stage` | `ocpitst0001` | `stage`    |
| prod  | `co2-calculator.epfl.ch`       | `svc1751p-co2-calculator-prod`  | `ocpitsp0001` | `main`     |

Each cluster has its own OpenShift console, ArgoCD and Grafana. All three
apps sit behind OpenShift Routes with TLS edge termination, labelled
`route: private`: reachable from the EPFL network or VPN only. The Route
uses the cluster's `*.epfl.ch` wildcard certificate; no certificate is
managed in our repos. Routing: `/` → frontend, `/api` → backend,
`/docs` → this site. The backend route carries a 10-minute HAProxy timeout
for SSE streams and long exports.

## What runs in a namespace

- **Frontend**: nginx serving the Quasar SPA. 2 to 3 pods (HPA on CPU),
  PodDisruptionBudget. Health: `/healthz`, `/ready`.
- **Backend**: FastAPI + Uvicorn, 2 to 3 pods (HPA), plus **one worker
  pod** running the same image with `OTEL_SERVICE_NAME=worker` for
  background jobs. No Redis, no broker: jobs are claimed in PostgreSQL
  ([ADR-010](../architecture-decision-records/010-background-job-processing.md),
  [ADR-015](../architecture-decision-records/015-claim-job-atomic-state-is-current.md)).
  Health: `/api/healthz` (liveness, always 200) and `/api/health/deps`
  (database and role provider, 503 on failure).
- **Docs**: this MkDocs site, 1 pod.
- **Migration Job**: `alembic upgrade head`, a Helm `pre-upgrade` hook, so
  a failed migration blocks the rollout.
- **OTel Collector**: receives OTLP from backend and worker. Metrics go to
  the cluster Prometheus through a `ServiceMonitor`; traces go to Tempo
  through `enac-it-otel`. The collector adds the `route_class` label, see
  [Observability & SLOs](03-observability-slo.md).
- **db-dump CronJob**: `pg_dump` daily at 02:00 into the `db-dumps` PVC,
  the only PVC in the namespace.
- **Monitoring CRs**: `PrometheusRule`, `AlertmanagerConfig` (email to
  the sysadmins group), Grafana dashboards.

Outside the namespace: PostgreSQL (EPFL DBaaS), S3 object storage,
Entra ID, EPFL's OPDo Elasticsearch (audit records, ISO 27701, see
[plan 240](../implementation-plans/240-feat-elastic-search.md)), Tempo,
Icinga, GlitchTip, Matomo. What each is for and how to
get access: [Tools and access](05-tools-and-access.md).

## How a change gets deployed

1. GitHub Actions builds the images into Quay (`quay-its.epfl.ch/svc1751`)
   and publishes the Helm chart from `helm/` to `ghcr.io`
   ([CI/CD Workflows](../architecture/cicd-workflows.md)).
2. A bot commit bumps the image tag in the GitOps overlay
   (`chore(manifest): update epfl/co2-calculator (<env>)`).
3. ArgoCD on that cluster auto-syncs and self-heals the
   `co2-calculator-<env>` application from `overlays/<env>`.

Per-environment values are `valuesInline` in the overlay's
`kustomization.yaml`; the chart itself is versioned and pinned there.
Rolling back is reverting the GitOps commit. The dev → stage → main
promotion is in the [Release runbook](../architecture/release-runbook.md).

## Configuration and secrets

Non-secret configuration is env vars in the overlay: `APP_*` for the
frontend, injected at container start by the image entrypoint, backend
settings by name. Secrets come from **Infisical through the External
Secrets Operator in all three environments**: one `ExternalSecret` pulls
every key under `/epfl/co2-calculator` into `backend-secret`, and separate
ones feed `db-secret`, `quay-reg-cred` and `docker-reg-cred`. Refresh
interval is 5 minutes; a changed value reaches the pods on the next
rollout restart. No secret is created by hand anymore. The key names
the backend reads are declared in `backend/app/core/config.py`; list what
is actually mounted with:

```bash
oc get secret backend-secret -n <namespace> -o json | jq '.data | keys'
```

Because of the wildcard, keys that only CI needs (release-please and
Codecov tokens, registry credentials) are mounted into the pods too.
Trim the Infisical folder, not this page.

## Backups and restore

- **Database**: the nightly dump above, plus DSI's own backups and
  point-in-time recovery under the
  [EPFL PostgreSQL SLA](https://go.epfl.ch/SVC1757). Restore procedure and
  the tools pod are in the private ops README.
- **Files**: S3 buckets are not versioned, by decision
  ([Recovery objectives](../architecture/security-documentation.md#recovery-objectives)).
  A lost CSV is re-uploaded.
- **Everything else**: the
  [Disaster Recovery Plan](https://github.com/EPFL-ENAC/openshift-app-config/blob/main/epfl/co2-calculator/DRP.md)
  (private).

## See also

- [Deployment Topology](../architecture/11-deployment-topology.md),
  [Environments](../architecture/05-environments.md),
  [Tech Stack](../architecture/08-tech-stack.md),
  [Scalability](../architecture/12-scalability.md)
- [CI/CD Pipeline](../architecture/06-cicd-pipeline.md) and
  [CI/CD Workflows](../architecture/cicd-workflows.md)
- [Observability & SLOs](03-observability-slo.md),
  [Frontend Error Monitoring](../frontend/error-monitoring.md),
  [OAuth http-callback post-mortem](02-postmortem-oauth-http-redirect.md)
- Vendor docs: [Kubernetes](https://kubernetes.io/docs/),
  [Helm](https://helm.sh/docs/), [ArgoCD](https://argo-cd.readthedocs.io/),
  [Prometheus](https://prometheus.io/docs/)

## Not here, on purpose

No Jaeger (removed 2026-06-17, traces live in Tempo), no Loki, no
Elasticsearch or Kibana **for logs** (the only Elasticsearch is EPFL's
OPDo audit sink above), no service mesh, no in-cluster PostgreSQL. If you
read otherwise elsewhere in these docs, that page is stale: fix it.

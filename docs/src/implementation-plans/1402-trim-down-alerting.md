---
status: proposed
issue: 1402
last_updated: 2026-07-07
title: "Split Grafana p99 Latency Alerting by Endpoint Class; Add GlitchTip Alerting"
summary: "Separate p99 latency alert thresholds for upload/job/pipeline endpoints from normal API calls, exclude SSE streams from duration-based alerting, and add error-rate alerting on GlitchTip."
---

# Split Grafana p99 Latency Alerting by Endpoint Class; Add GlitchTip Alerting

## Problem

The current Grafana p99-latency alert evaluates request duration across
**all** backend HTTP traffic with a single threshold. CSV upload
(`POST /api/v1/files`), pipeline dispatch/recalculation
(`POST /api/v1/sync/dispatch`, `/sync/units`, `/sync/units/recalculate*`,
`year-configuration` recalculation triggers), and job/pipeline polling
under `/api/v1/sync/*` are naturally slow (multi-second to multi-minute
ingestion work) and trip the alert on every use — which trains the team to
ignore it. Two SSE endpoints, `GET /sync/jobs/{job_id}/stream` and
`GET /sync/pipelines/{pipeline_id}/stream` (`backend/app/api/v1/data_sync.py:1378,1811`),
are long-lived connections; "duration" for a stream is meaningless and
will dominate any p99 bucket it's counted in.

No alert-rule or dashboard IaC exists in this repository. Grafana
dashboards/alert rules are provisioned in the ops repos
(`enack8s-app-config` / `openshift-app-config`) — referenced only by
comment in `helm/values.yaml:217`. This repo's own observability surface
is: (1) an OTel Collector scaffold in `docker-compose.yml` (OTLP receiver
→ Prometheus exporter on `:9464`, `otel/otel-collector-config.yaml`) with
no OTel SDK instrumentation wired into `backend/app` — the request-duration
histogram driving the current alert is produced by the ingress/router
layer (Traefik in compose, presumably the cluster ingress in prod), keyed
on path/router labels, not by in-process spans; and (2) frontend error
capture only — `@sentry/vue` in `frontend/src/boot/sentry.ts`, wired to
EPFL's self-hosted GlitchTip, `tracesSampleRate: 0.05`. The backend has
**no** Sentry/GlitchTip SDK (grep hits on "sentry" in `backend/app` are
false positives — `StaleStatsEntry`, `RecalculationStatusEntry` substring
matches). No GlitchTip alert rule (new-issue / error-rate notification) is
configured for the existing frontend project.

## Design

Path-based split is sufficient — no new backend instrumentation needed.
Route prefixes are already stable and semantically grouped
(`backend/app/api/router.py`):

- **Job/upload/pipeline group** (slow-by-design, alert on abuse/regression
  only): `POST /api/v1/files` (CSV upload), `/api/v1/sync/*` excluding the
  two stream routes (`dispatch`, `units`, `jobs/*`, `pipelines`, `workers`,
  `active-pipelines*`, `recalculation-status`), `/api/v1/year-configuration`
  recalculation-trigger POSTs.
- **Normal API group** (everything else): CRUD/read endpoints — `/units`,
  `/factors`, `/taxonomies`, `/carbon-reports`, `/modules*`, `/backoffice*`,
  `/locations`, `/audit`, `/workspace`, `/unit`, `/users`, `/auth`,
  `/session`.
- **Excluded from latency alerting entirely**: `GET /sync/jobs/{job_id}/stream`
  and `GET /sync/pipelines/{pipeline_id}/stream` — SSE, unbounded duration
  by design. If connection health needs monitoring later, do it via
  connection-count/error-rate, not duration.

Two alert groups replace the single rule, both defined in the ops repo
against the existing ingress/router-labeled duration histogram (exact
metric name to be confirmed against what the ops repo's current rule
already queries, since this repo doesn't own that config):

| Group                | Path match                                                                       | p99 threshold                                   | Eval window                                                        |
| -------------------- | -------------------------------------------------------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------ |
| Normal API           | not upload/sync/year-configuration-recalc paths, not `*/stream`                  | existing threshold (tight, e.g. 1-2s)           | existing                                                           |
| Jobs/upload/pipeline | `/files`, `/sync/*` (minus `/stream` routes), `/year-configuration/*recalculat*` | looser (e.g. 30-60s, tune from historical data) | longer (e.g. 15m) to smooth over legitimately bursty large uploads |

GlitchTip alerting: add a project alert rule on the existing frontend
GlitchTip project — new-issue notification and an error-rate-spike rule
(e.g. >N new events/5min) routed to the team's existing notification
channel (Slack/email — whatever the ops repo already uses for Grafana
alerts, for consistency). This is a GlitchTip project setting (UI/API on
the hosted instance), not code in this repo — no SDK change needed.
Backend error tracking (no Sentry/GlitchTip SDK exists there today) is out
of scope for this issue; flag as a follow-up if backend 5xx visibility is
needed beyond what's already surfaced via the frontend's HTTP-5xx
`captureMessage` path (`frontend/src/api/http.ts`).

## Steps

- [ ] Confirm in the ops repo (`enack8s-app-config` / `openshift-app-config`)
      which metric/labels the current p99 alert queries (ingress duration
      histogram, labeled by path or router name) — this repo has no
      visibility into that config.
- [ ] Pull 2-4 weeks of historical p99 for `/files` and `/sync/*` (excluding
      `/stream` routes) from existing dashboards to set a realistic
      threshold for the jobs/upload/pipeline group (don't guess a number
      the team will immediately silence).
- [ ] In the ops repo, split the single alert rule into two: normal-API
      (keep existing threshold) and jobs/upload/pipeline (new looser
      threshold + longer eval window), both excluding `*/stream` paths.
- [ ] Exclude `/sync/jobs/{job_id}/stream` and `/sync/pipelines/{pipeline_id}/stream`
      from both latency alert groups (path-negative match).
- [ ] Configure a GlitchTip alert rule on the frontend project: new-issue
      notification + error-rate-spike threshold, routed to the same
      channel as the Grafana alerts.
- [ ] Document the two alert groups and thresholds in a short ops note, so
      the split isn't tribal knowledge living only in the ops repo.
- [ ] Verify: trigger a CSV upload and a normal read endpoint in
      stage/prod-like env, confirm only the jobs/upload/pipeline group's
      threshold applies to the upload and the normal-API group stays tight
      for the read call; confirm the SSE stream endpoints never fire either
      alert regardless of connection duration.

---
status: delivered
issue: 3023
last_updated: 2026-11-10
summary: LatencyP95High and LatencyP99High read the same on dev, stage and prod (P95 > 5000 ms, P99 >= 10000 ms, both bucket edges) and only fire above 100 API requests in 5 minutes; P99 uses >= because 10000 ms is the top finite bucket
---

# 3023 — same latency alerts on all three environments

## Problem

The two app latency alerts in the osac overlays
(`epfl/co2-calculator/overlays/{dev,stage,prod}/monitoring/specific-namespace-alerts.yaml`)
had drifted:

| Env   | P95 / P99 before | Aggregation                 |
| ----- | ---------------- | --------------------------- |
| dev   | 5000 / 10000 ms  | `sum by (le)`               |
| stage | 2000 / 4000 ms   | `sum by (le, k8s_pod_name)` |
| prod  | 2000 / 4000 ms   | `sum by (le)`               |

2000 and 4000 are not bucket edges (the HTTP histogram uses the OTel default
buckets, 25/50/75 per decade), so the quantile was interpolated there. No
environment had a volume guard, so a few slow requests on a quiet platform
could fire the alert.

## Decision

Agreed on the issue on 2026-10-05, refined on 2026-11-10:

- P95 > 5000 ms and P99 >= 10000 ms on all three environments.
- Both rules also need
  `sum(increase(http_server_duration_milliseconds_count{namespace="<ns>", route_class="api"}[5m])) > 100`.
- `for: 5m`, `severity: warning` and the runbook links are unchanged.

**Why `>=` on P99.** The backend sets no histogram view, so 10000 ms is the
highest finite bucket. When the quantile falls in `+Inf`, `histogram_quantile`
returns that edge, so it never exceeds 10000 and dev's old `> 10000` could
never fire. Plan [1402](1402-trim-down-alerting.md) saw the same saturation
on the job routes. `>= 10000` fires when at least 1% of API requests take
10 s or more.

**Why stage loses its per-pod grouping.** The volume guard is a label-less
`sum`, and `and` matches on labels, so a per-pod quantile would never match it
and the stage alert would never fire. The other alerts had already moved to a
global aggregate, see [observability SLO](../infra/03-observability-slo.md).
The description's `{{ $labels.pod }}` goes with it.

## What shipped

- osac: the two rules in the three overlays, identical apart from the
  namespace. Checked by diffing the rule blocks with the namespace replaced
  by a placeholder.
- co2-calculator: the alert catalog row in
  `docs/src/infra/03-observability-slo.md` and the alert list in
  `docs/src/architecture/release-management.md` state the new thresholds.

No backend change. `promtool` is not available locally, so the PromQL was
not machine-checked; it reuses dev's existing quantile and a counter the prod
dashboard already queries.

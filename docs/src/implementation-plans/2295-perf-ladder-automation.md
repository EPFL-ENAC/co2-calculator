---
status: delivered
issue: 2295
last_updated: 2026-09-25
summary: "make perf-ladder runs a warm-up plus a stage ladder for one named
  config against dev, then make perf-summary computes backend CPU
  milliseconds per request per stage: cAdvisor CPU-seconds over the steady
  window divided by locust's own request count, never an OTel counter."
---

# Perf ladder + CPU per request (#2295)

**Goal:** one command per config under test, and a correct backend CPU
cost per request for each stage. Before this, someone ran a stage, waited,
ran the next one, then queried Grafana by hand.

## Why the denominator is locust's

The OTel metrics (`http_server_*`, `db_pool_*`, `db_server_*`) are pushed
every ~60 s and lag. On 24 Sep the OTel request rate read about half of
locust's, alternated 0/33/0/69 between 30 s samples, and still showed 109
in-flight requests after the run had ended. A ratio with that denominator
is noise. So:

- **denominator:** locust's cumulative `Aggregated` request count from
  `<tag>_stats_history.csv`, over the steady window;
- **numerator:** `sum(increase(container_cpu_usage_seconds_total{container="backend"}[W]))`
  (cAdvisor) at the window end, over the same window;
- OTel gauges appear only as maxima, labelled coarse.

## Design

- **Steady window** (`steady_window`): from the first history row at the
  final user count, plus 15 s to settle, to the last row with users still
  running. Two cases are handled because both occur in real report files:
  - rows at 0 users after the run (PERF_UI idling) are dropped;
  - VUs lost mid-run lower the final count, so the window uses that count.
- **Minimum window 60 s**: cAdvisor is scraped every 30 s, and `rate()`
  needs two scrapes. A shorter window fails hard, before any network call.
- **Slices are 60 s, not 30 s**: this deviates from the brief. A `rate()`
  over one 30 s scrape interval returns nothing. Each slice is the
  trailing 60 s at a Prometheus step, stepped every 30 s, and divided by
  the locust requests in that same 60 s. The median and p95 across slices
  show how stable the ratio is over time. They are not per-request
  percentiles.
- **Pods**: the same `sum by (pod) (rate(...[60s]))` range query gives the
  busiest pod's peak, the mean pod CPU, and their ratio.
- **Throttling**: throttled ÷ total CFS periods. cAdvisor emits CFS
  counters only for a container with a CPU limit, and the chart sets none.
  No series, or 0 periods, shows "no CPU limit", never `nan`. The usage
  query on the same selector has already proven it matches.
- **Fleet**: backend HPA replicas min/max, `max(db_server_connections)`,
  and the `checked_out` maximum of backend pods' `db_pool_connections`.
- **Failures**: a 401/403 from Grafana raises "Grafana session expired or
  token invalid". An empty or ambiguous Prometheus result raises too.
  No table is printed until every tag is complete.
- **Locust bootstrap**: `/v1/session` and `/v1/units` go through
  `_bootstrap_json`. A non-2xx or non-JSON answer is recorded as a failure
  and the VU stops with `StopUser`. Before, it crashed its greenlet with a
  JSONDecodeError, at 500 and 800 users on 24 Sep. Locust 2.46 still logs
  one error line per stopped VU, because it logs every `on_start`
  exception.

## What shipped

- `backend/tests/performance/infra_summary.py`: stdlib only. Pure
  functions (window, slices, ms/request, pod stats) are separate from the
  Prometheus client.
- `backend/Makefile`: `perf-ladder` and `perf-summary`. The Grafana URL,
  datasource uid and namespace are overridable variables.
- `backend/tests/unit/test_perf_infra_summary.py`: window, slice and
  ms/request math, the no-CPU-limit throttling case and the 401/403
  path.
- `backend/tests/performance/README.md`: "Ladder + infra summary".

## How to run

```bash
cd backend
export GRAFANA_TOKEN=<service-account token>   # or GRAFANA_SESSION=<cookie>
make perf-ladder PERF_LADDER_TAG=pool70_base   # warm-up, 100 and 600 users x 3 min
make perf-summary PERF_SUMMARY_TAGS="dev_pool70_base_100 dev_pool70_base_600"
```

The cooldown between stages defaults to 60 s. It stays below the HPA's
default 300 s scale-down stabilization, since the chart sets no
`behavior`, so the fleet stays warm from one stage to the next.

## Verified

- Dry-ran the window math offline on the 24 Sep report files:
  - `dev_pool70_before_100`: 34 s window, 1060 requests, 31.2 rps;
  - `dev_pool70_before_600`: 34 s window, 4864 requests, 143.1 rps.
  - Both were 1-minute stages, so the summary refuses them. Rerun them
    through the ladder.
- The 3-minute `dev_explorerreaduser_50` and `_100` give windows of 155 s
  and 153 s, each with four slices.
- Not verified: the live Prometheus queries, and whether the HPA series
  exists under that name.

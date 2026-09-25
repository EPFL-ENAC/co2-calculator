---
status: delivered
issue: 2295
last_updated: 2026-09-25
summary: "Local, in-process harness that measures CPU ms per request (mean,
  median, p95), wall ms, SQL statements, pool checkouts and OTel spans per
  endpoint of the ExplorerReadUser mix, at three tracing levels driven by
  the pods' own OTEL_* env vars, with an optional cProfile pass that splits
  CPU by component (SQLAlchemy, psycopg, pydantic, Starlette/FastAPI,
  OpenTelemetry, app code)."
---

# CPU per request, per endpoint (#2295)

## Why

The 24 Sep dev load ladder saturated on **backend CPU**: about 30 ms of CPU
per request on single-worker, 1-core pods, so fleet capacity is roughly
cores ÷ CPU per request ≈ 150 req/s. Prometheus only gives a fleet mean. This
harness gives the per-endpoint number and shows where the CPU goes. It tests
two hypotheses:

- **Statement count dominates.** Each statement costs ORM, driver and, on
  dev, a span.
- **Pydantic serialisation** of the stats JSON takes a large share.

## Design

`backend/tests/performance/cpu_profile.py` (I/O) and `cpu_profile_stats.py`
(pure statistics, bucketing, markdown; unit-tested in
`tests/unit/performance/test_cpu_profile.py`).

- **In process, sequential.** `httpx.ASGITransport` drives `app.main:app`
  one request at a time. The `time.process_time()` delta around a request
  is that request's CPU. The delta covers the whole process: it includes
  the OTel exporter threads and the in-process httpx client. `healthz` is
  the floor row: middleware and harness, no auth, no SQL.
- **Endpoints** are `ExplorerReadUser`'s tasks from `locustfile.py`, under
  the same names, plus `session`. Units and years come from
  `/v1/session`, and each request cycles through them deterministically.
  Merged queries take the first `PERF_MERGED_UNITS` (10) units. The
  principal login has only 4 leaf units, so merged queries use 4.
  `explore_read` 404s until a sandbox exists, so the harness POSTs one per
  unit first, like the SPA does.
- **Real auth.** One `GET /v1/auth/login-test` (DEBUG builds only, refused
  loudly otherwise), then its cookie on every request. Each request
  therefore pays JWT decode plus user lookup.
- **Counters.** SQLAlchemy `before_cursor_execute` (the statement-budget
  tests' listener) counts statements. The pool `checkout` event counts
  checkouts, each of which also runs an uncounted pre-ping. A span
  processor counts spans.
- **No lifespan.** Nothing on the read path needs it. Handlers bootstrap
  lazily, and nothing reads the DB-health cache. Running it would add
  `init_db` DDL and background loops whose CPU would land in the deltas.
- **Safety.** The harness refuses to start unless `get_settings().DB_URL`
  is Postgres on `localhost`, `127.0.0.1` or `::1`. There is no override
  flag.

## Levels

Each level runs in a child process started like the Dockerfile CMD, under
`opentelemetry-instrument`. The child gets the instrumentations that
`opentelemetry-bootstrap -a requirements` lists, layered with
`uv run --with-requirements`, so `pyproject.toml` is untouched. The local
venv on its own has only the FastAPI and ASGI instrumentations, which would
make `dev` identical to `prod`.

| level  | env                                                                                               |
| ------ | ------------------------------------------------------------------------------------------------- |
| `off`  | `OTEL_SDK_DISABLED=true` (hooks still wrap the app with no-op spans)                              |
| `prod` | `OTEL_TRACES_SAMPLER=always_on`, `OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=httpx,sqlalchemy,psycopg` |
| `dev`  | `OTEL_TRACES_SAMPLER=always_on`, `OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=httpx,sqlalchemy`         |

- **httpx is disabled at every level.** Its instrumentation would wrap the
  harness's own client, and the read path makes no httpx calls.
- **Each worker checks its own instrumentation.** It verifies that the
  spans it sees match its level (no spans, server spans only, or
  per-statement DB spans) and fails if they don't.
- **Exporters.** `--exporter otlp` (the default) sends traces and metrics
  to the compose collector on `localhost:4317`, as the pods do.
  `--exporter none` creates the spans but exports nothing.
- **Log level.** `LOG_LEVEL` defaults to `INFO` (stage and prod). Dev pods
  run `DEBUG`; pass `--log-level DEBUG` to measure that separately.

`--profile <endpoint>` runs a **separate** cProfile pass after the
measurement, so profiler overhead never reaches the table. Its timer is
wall clock, so time blocked in the selector gets its own "io wait" row and
is left out of the CPU shares. Only the event-loop thread is profiled. The
`.prof` file lands in `reports/`.

## How to run

From `backend/`, with the local compose Postgres seeded:

```bash
docker compose up -d otel        # repo root; or add --exporter none
uv run python -m tests.performance.cpu_profile                  # off, prod, dev
uv run python -m tests.performance.cpu_profile --levels prod -n 200
uv run python -m tests.performance.cpu_profile --levels dev --profile merged_report_stats
uv run python -m tests.performance.cpu_profile --exporter none  # span creation only
```

Output is a markdown table per level on stdout, and
`reports/cpu_profile_<level>.json` / `.log` (gitignored).

## Data-presence prerequisite

Hand this to psql on the **local** DB before the first run:

```sql
WITH years AS (
  SELECT year FROM year_configuration WHERE provider = 'TEST' AND is_started
)
SELECT u.institutional_id, y.year,
       count(DISTINCT cr.id) AS calculator_reports,
       bool_and(coalesce(cr.stats::text, 'null') <> 'null') AS has_stats,
       count(de.id) AS data_entries
FROM units u
CROSS JOIN years y
LEFT JOIN carbon_projects cp
  ON cp.unit_id = u.id AND cp.carbon_report_type = 'Calculator'
LEFT JOIN carbon_reports cr
  ON cr.carbon_project_id = cp.id AND cr.year = y.year
LEFT JOIN carbon_report_modules crm ON crm.carbon_report_id = cr.id
LEFT JOIN data_entries de ON de.carbon_report_module_id = crm.id
WHERE u.institutional_id IN ('13032', '13033', '13034', '13035')
GROUP BY u.institutional_id, y.year
ORDER BY u.institutional_id, y.year;
```

**Ready** means one row per leaf unit × started TEST year, each with
`calculator_reports >= 1`, `has_stats = true` and `data_entries > 0`. Zero
rows or any zero count means not ready: run `make perf-seed`.

`user_provider_enum` is stored by member name (`'TEST'`).
`carbon_report_type_enum` is stored by value (`'Calculator'`) because of
its `values_callable`. `stats` is a `json` column, so a JSON `null` counts
as missing too.

# Performance suite (#2295)

Load tests (locust) and a table-endpoint latency matrix for the CO₂
calculator backend. Full guide:
[docs/src/backend/load-testing.md](../../../docs/src/backend/load-testing.md).
Design history: implementation plans `2295-load-tests-locust.md` and
`2295-table-pagination-sort-matrix.md`.

## Quickstart (local)

```bash
# backend/.env → DB_URL=postgresql://co2_user:co2_password@localhost:5432/co2_calculator?sslmode=disable
make run-db && cd backend && make db-migrate
make perf-seed          # 600 units × 2021-2025 × 0.1 ceilings ≈ 6M entries
make perf-csvs          # upload CSVs from real factor data
make perf-db-dump       # snapshot; perf-db-restore skips future re-seeds

uv run uvicorn app.main:app --port 8010 --workers 4 &   # NOT --workers 1

make perf-load PERF_HOST=http://127.0.0.1:8010 PERF_USERS=50 PERF_CLASSES=ExplorerReadUser
make perf-sweep PERF_HOST=http://127.0.0.1:8010          # full ladder (~90 min)
make perf-table-matrix PERF_HOST=http://127.0.0.1:8010   # every submodule × limit × sort
make perf-report                                         # p95 > 1s table
```

Runs are headless by default; `PERF_UI=1 make perf-load …` (or `perf-dev`)
keeps locust's web UI at http://127.0.0.1:8089 with live charts - the run
still autostarts with the same users/rate/duration, locust stays up until
Ctrl-C, and the report is written when it quits. Each run prints its
target up front and a `report: file://…html` line at the end; open that.
Reports land here in `reports/` (gitignored): one `*_stats.csv` + `*.html`
per stage, `table_matrix.csv` for the matrix.

## Against dev, clef en main

```bash
make perf-dev                                         # 50 × ExplorerReadUser, 3 min
make perf-dev PERF_USERS=200 PERF_CLASSES=ModuleReadUser
make perf-report
```

That is the whole recipe. `perf-dev` targets `PERF_DEV_HOST`
(`https://co2-calculator-dev.epfl.ch/api` — the `/api` prefix matters:
the bare host is the SPA and answers every path with `index.html`),
logs each VU in through `/v1/auth/login-test` (dev is a DEBUG build, so
the endpoint exists), and refuses `PlanUser` / `ExploreCreateUser` /
`CsvUploadUser` unless `PERF_ALLOW_WRITES=1` — those enqueue real jobs
on dev's worker pods. Reports land in `reports/dev_*`.

`PERF_ROLE` still applies (`PERF_ROLE=calco2.user.standard make perf-dev`).
Seeded-user JWT minting is local-only: it needs the target's
`JWT_HMAC_KEY`, so `perf-dev` switches it off.

If a target has **no** `login-test` (stage, prod, or dev with
`DEBUG=false`), copy the `auth_token` cookie from a logged-in browser
tab (DevTools → Application → Cookies) and pass it explicitly — it takes
precedence over every other auth path:

```bash
PERF_AUTH_COOKIE='eyJ...' make perf-load PERF_HOST=https://<host>/api PERF_CLASSES=ExplorerReadUser
```

All VUs then share that one identity, so unit scoping is that user's.

## Ladder + infra summary

One command per config under test, against dev by default:

```bash
export GRAFANA_TOKEN=<service-account token>   # or GRAFANA_SESSION=<grafana_session cookie>
make perf-ladder PERF_LADDER_TAG=pool70_base
make perf-summary PERF_SUMMARY_TAGS="dev_pool70_base_100 dev_pool70_base_600"   # older tags, or a rerun
```

- `PERF_LADDER_TAG` is required: it names the config, e.g. `pool70_base`.
  The ladder runs a warm-up (`<tag>_warmup`, 50 users × 60 s, not
  summarised), then each `PERF_LADDER` stage (default `100 600`) for
  `PERF_LADDER_TIME` (default `3m`) as `<tag>_<users>`. `perf-dev` adds
  the `dev_` prefix and keeps its write guard.
- Stages are `PERF_LADDER_COOLDOWN` s apart (default 60). That stays well
  under the HPA's default 300 s scale-down window, so the fleet stays warm.
- A failed stage stops the ladder. With credentials set, the summary runs
  one cooldown after the last stage, once the OTel export has caught up.
  Without them, the ladder prints the `make perf-summary` command to run.
- Stages last 3 minutes because Prometheus scrapes cAdvisor every 30 s.
  The summary refuses a steady window under 60 s: a 1-minute stage leaves
  about 34 s.
- Credentials come only from `GRAFANA_TOKEN` (Bearer) or `GRAFANA_SESSION`
  (the `grafana_session` cookie of a logged-in tab). A copied cookie can
  expire during a 10-minute ladder, so use a token for unattended runs.
  A 401/403 fails hard: export a fresh one and rerun `perf-summary`.
  Override `GRAFANA_URL`, `GRAFANA_DATASOURCE_UID` or `PERF_NAMESPACE` to
  point it elsewhere.

The summary prints one markdown table, one column per tag, and writes
`reports/<tag>_infra.json`:

| Row                                           | Meaning                                                                                                                 |
| --------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| steady window                                 | First history row at the final user count, plus 15 s to settle, to the last row with users running                      |
| requests / failures / rps in window           | Locust's cumulative `Aggregated` counters over that window: the denominator                                             |
| p50 / p95 / p99, failures (whole run)         | `<tag>_stats.csv` aggregate, ramp-up included                                                                           |
| backend CPU-seconds                           | `sum(increase(container_cpu_usage_seconds_total{container="backend"}[window]))` at the window end                       |
| **CPU ms / request**                          | 1000 × CPU-seconds ÷ locust requests in the window                                                                      |
| slice stability: median / p95                 | The same ratio over 60 s trailing slices stepped every 30 s. It shows spread over time, **not** per-request percentiles |
| busiest pod / mean pod CPU, imbalance         | Per-pod CPU (cores) over the window: the peak, the mean of every pod sample, and their ratio                            |
| CPU throttled share                           | Throttled ÷ total CFS periods; "no CPU limit" when cAdvisor has no CFS series (no quota)                                |
| HPA replicas                                  | Min–max of the backend HPA's current replicas                                                                           |
| DB server connections, pod pool `checked_out` | Maxima of OTel gauges: coarse, exported every ~60 s and lagging                                                         |

Why locust counts the requests: the OTel request counters export every
~60 s and lag. On 24 Sep they read about half of locust's rate and
alternated 0/33/0/69 between samples. Locust's count includes failed
requests, and the `FLOW` rows of the Plan and Upload scenarios. The
history CSV cannot separate either, so read CPU per request on the
read-only classes.

## `backend/.env`'s `DB_URL` may not be localhost

`DB_URL` may point at a shared platform DB (e.g. `co2-dev.xxxx.epfl.ch`), not
local compose — real backend/worker pods are already on it. Run in order:

- [ ] `psql "$DB_URL" -tAc "select count(*) from data_entries"` — 0 → seed
      below; >0 → backdrop already there, skip straight to starting the backend
- [ ] `SEED_ALLOW_REMOTE=1 make perf-seed` — refuses to run without the flag
      ("unrecoverable" per `seed_all.py`); if units/reports/factors already
      exist but `data_entries` was 0, resume with just
      `SEED_ALLOW_REMOTE=1 uv run python -m app.seed.random_generator.seed_data_entries`
- [ ] `psql "$DB_URL" -tAc "show max_connections"` and `... "select count(*) from pg_stat_activity"`
      — pick `--workers` × (`DB_POOL_SIZE`+`DB_MAX_OVERFLOW`) with headroom below the gap
- [ ] add `RUN_BACKGROUND_POLLER=False` to `.env` — backend won't start
      against a remote host otherwise (#2220)
- [ ] `DB_POOL_SIZE=10 DB_MAX_OVERFLOW=5 uv run uvicorn app.main:app --port 8010 --workers 2`
      (numbers from the connection check above, not compose's `--workers 4`)
- [ ] `make perf-load PERF_HOST=http://127.0.0.1:8010 PERF_DB_URL=$DB_URL PERF_CLASSES=ExplorerReadUser`
- [ ] `make perf-table-matrix PERF_HOST=http://127.0.0.1:8010 PERF_DB_URL=$DB_URL`
- [ ] skip `perf-sweep`'s `PlanUser`/`ExploreCreateUser`/`CsvUploadUser` stages —
      they'd enqueue real jobs for the live worker pods to execute

## What's in this folder

| File                      | Purpose                                                                                                                                                                   |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `locustfile.py`           | The load scenarios: `ExplorerReadUser`, `ModuleReadUser`, `ExploreCreateUser`, `PlanUser`, `CsvUploadUser`                                                                |
| `table_matrix.py`         | Exhaustive table-endpoint sweep: every submodule × limit {20,100,500,1000} × every sort column × order, plus filter search, deep pagination, item GETs, chart companions  |
| `perf_common.py`          | Shared helpers (JWT minting, sort-column discovery) — importable without locust                                                                                           |
| `report_slow.py`          | Scans stage CSVs for endpoints with p95 over a threshold                                                                                                                  |
| `infra_summary.py`        | `make perf-summary`: backend CPU ms per request per stage (cAdvisor ÷ locust), pod imbalance, throttling, HPA replicas, DB gauges                                         |
| `pipeline_connections.py` | Samples `pg_stat_activity` while one upload per module type runs (`--parallel N` for N units at once): held connections per pipeline phase, for the connection budget doc |

## How auth works

Every virtual user is a **distinct seeded DEFAULT-provider user**:
`make perf-load` derives `reports/perf_users.txt` from the DB and each VU
mints its own `auth_token` (same `JWT_HMAC_KEY` as the target). Without
that file (dev), `login-test` runs **once per role per locust process** and
VUs share the cookie: N concurrent logins upsert one test-user row and
serialise on its lock while holding bouncer slots (200 logins = 43 s max). Principal
users drive module reads/uploads/plans; standard users only own
travel/cloud entries. Against a remote host, export
`PERF_AUTH_COOKIE=<auth_token JWT>` instead (login-test only exists on
DEBUG builds). Read the multi-request `FLOW` rows for plan-lifecycle and
upload-to-ingested wall times, and always p95/p99, never averages.

## Local ceilings to know about (found the hard way)

- 4 workers × (`DB_POOL_SIZE` + `DB_MAX_OVERFLOW`) must stay under
  Postgres `max_connections` — compose now sets 200 (+ `shm_size: 1gb`
  for `limit=1000` sorts). Recreate the container to apply, not just
  restart.
- One uvicorn worker benchmarks a Python process, not the app.
- Run long sweeps in your own terminal/tmux, or detached (`nohup`) — a
  Claude/CI session's background children die with the session.

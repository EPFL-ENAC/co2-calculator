# Load testing (locust)

Find the endpoints that exceed 1 s under realistic concurrency. Locally
first; then against dev, whose DB is ~10× slower. Design and delivered
scope: [implementation plan 2295](../implementation-plans/2295-load-tests-locust.md).

## One-time setup (local)

Point `backend/.env` at the **local** database first — the seeder refuses
non-local hosts:

```bash
DB_URL=postgresql://co2_user:co2_password@localhost:5432/co2_calculator?sslmode=disable
```

Then, from the repo root and `backend/`:

```bash
make run-db                # compose Postgres on :5432
cd backend
make db-migrate
make seed-data             # locations, rooms, factors (needs INPUT_DATA/)
make perf-seed             # backdrop: 600 units × 2021–2025 × 0.1 ceilings ≈ 6M rows
make perf-csvs             # upload CSVs sampled from real factor data
make perf-db-dump          # snapshot the backdrop for cheap re-runs
```

Re-runs: `make perf-db-restore` instead of re-seeding. Knobs:
`SEED_NUM_UNITS`, `SEED_YEARS`, `SEED_CEILING_SCALE` (1 = the full #2161
worst case, ≈63M rows — plan for a long seed).

## Running

Start the backend with several workers — one worker benchmarks a single
Python process, not the app:

```bash
cd backend && uv run uvicorn app.main:app --workers 4 --port 8000
```

Then:

```bash
make perf-load PERF_USERS=50 PERF_CLASSES=ExplorerReadUser   # one stage
make perf-sweep                                              # full ladder
make perf-report                                             # p95 > 1s table
```

`perf-sweep` runs reads at 50/100/200/500/1000 users, plan and
explore-report creation at 10/20/30/40, and parallel CSV uploads at
5/10/20. Each stage writes a CSV + HTML report to
`backend/tests/performance/reports/` (gitignored). Read the **p95/p99**
columns, not averages.

### Scenarios

Pick with `PERF_CLASSES` (class names in
`backend/tests/performance/locustfile.py`):

| Class               | Simulates                                                                                                |
| ------------------- | -------------------------------------------------------------------------------------------------------- |
| `ExplorerReadUser`  | Dashboard/explorer read mix: workspace home, merged modules-stats, unit totals, module + submodule reads |
| `ExploreCreateUser` | Parallel Simulator-Explore report creation                                                               |
| `PlanUser`          | Project-plan lifecycle: create → reference year (prefill job) → read → delete                            |
| `CsvUploadUser`     | CSV upload → dispatch → poll ingestion pipeline to completion                                            |

Multi-request flows (plan lifecycle, upload-to-ingested) also report their
total wall time as `FLOW` rows in the stats.

### Knobs (env)

`PERF_HOST`, `PERF_USERS`, `PERF_TIME`, `PERF_ROLE` (default
`calco2.backoffice.admin` — global scope), `PERF_MERGED_UNITS`,
`PERF_JOB_TIMEOUT`, `PERF_AUTH_COOKIE`.

## Against dev

```bash
make perf-load PERF_HOST=https://<dev-host> PERF_USERS=50
```

`login-test` only exists on DEBUG builds. If dev runs without it, copy an
`auth_token` cookie from a browser session and export
`PERF_AUTH_COOKIE=<jwt>`. Uploads and plan prefills create real data —
coordinate before pointing write scenarios at a shared environment.

## Interpreting results

- The budget: p95 under 1 s per endpoint at the target concurrency
  (guardrails' normal-load budget is stricter — see
  [guardrails](../contributing/guardrails.md)).
- A stage where _everything_ degrades together usually means a saturated
  resource (worker CPU, DB pool), not one slow endpoint — check pool size
  and worker count before filing per-endpoint issues.
- Known measurement caveats (placeholder emissions in the backdrop, one
  shared test user per role) are listed in the
  [implementation plan](../implementation-plans/2295-load-tests-locust.md).

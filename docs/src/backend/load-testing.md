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
worst case, ≈63M rows — plan for a long seed), `SEED_CEILING_UNITS_PREFIX`
(default `U0`: only the fake perf units get ceiling data, so a DB that also
holds real accred-synced units doesn't balloon).

If your host `pg_dump`/`pg_restore` is older than the server (compose runs
Postgres 18), dump through the container instead:
`docker exec co2-calculator-postgres pg_dump -U co2_user -Fc co2_calculator > dump`.

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

| Class               | Simulates                                                                      |
| ------------------- | ------------------------------------------------------------------------------ |
| `ExplorerReadUser`  | Dashboard/explorer read mix: workspace home, merged modules-stats, unit totals |
| `ModuleReadUser`    | Module + paginated submodule page reads                                        |
| `ExploreCreateUser` | Parallel Simulator-Explore report creation                                     |
| `PlanUser`          | Project-plan lifecycle: create → year range + prefill job → read → delete      |
| `CsvUploadUser`     | CSV upload → dispatch → poll ingestion pipeline to completion                  |

Multi-request flows (plan lifecycle, upload-to-ingested) also report their
total wall time as `FLOW` rows in the stats.

### Roles and the order of creation

Uploads require an **opened year configuration** — normally the backoffice
admin's `bootstrap-years`; `make perf-seed` stamps it directly for the
DEFAULT and TEST providers, so login-test users see the seeded years.

Merged stats, module reads and uploads are scoped to the caller's unit
memberships and `modules.*` permissions, so the **unit roles are the
drivers**: `calco2.user.principal` (default) and `calco2.user.standard`.
Their login-test scopes cover the four TEST leaf units; the perf seeder
maps its first four fake units onto those iids so both roles own
ceiling-loaded units. Note the permission split: a standard user carries
only `.../own` permissions on travel and cloud/AI plus `planner.plans`, so
module reads and bulk uploads run as principal; rerun the read/plan
ladders as standard with `PERF_ROLE=calco2.user.standard make perf-load ...`.

The backoffice admin (`calco2.backoffice.admin`) has **no memberships and
no `modules.*` permissions** — use it only for workspace-home/totals reads
across the full seeded pool: `make perf-load` auto-derives `PERF_UNIT_IDS`
from the local DB (or pass ranges like `PERF_UNIT_IDS=4403-5002`).

### Knobs (env)

`PERF_HOST`, `PERF_USERS`, `PERF_TIME`, `PERF_ROLE` (default
`calco2.user.principal`), `PERF_UNIT_IDS` (explicit unit-id pool for roles
without memberships), `PERF_MERGED_UNITS`, `PERF_JOB_TIMEOUT`,
`PERF_AUTH_COOKIE`.

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

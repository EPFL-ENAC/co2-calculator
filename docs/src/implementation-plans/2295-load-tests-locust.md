---
status: delivered
issue: 2295
last_updated: 2026-08-29
summary: "Locust load-test suite: staged concurrency (50→1000 readers,
  10→40 plan/explore creators, 5→20 parallel CSV uploads) against a
  COPY-seeded backdrop of N units × N years at #2161 ceiling density,
  with make targets for seeding, sweeping, reporting p95>1s, and
  dumping/restoring the seeded DB."
---

# Load tests with locust (#2295)

**Goal:** find which endpoints exceed 1 s under realistic concurrency,
locally first, then against the dev platform (~10× slower DB).

Complementary to the #2161 plan (single-request, in-process, one unit at
ceiling): this suite is real HTTP against a running stack, many units, many
concurrent users.

## What shipped

- `backend/app/seed/ceilings.py` — #2161's per-type ceilings as code
  (single source; `scripts/generate_perf_test_csvs.py` now derives its
  `CEILINGS` from it). Pinned by `tests/unit/seed/test_ceilings.py`.
- `backend/tests/performance/locustfile.py` — rewritten (old file was dead
  scaffolding hitting nonexistent `/api/v1/users`). Four scenarios:
  `ExplorerReadUser` (workspace home, merged modules-stats, unit totals,
  module/submodule reads, explore GET), `ExploreCreateUser`,
  `PlanUser` (create → set reference year → poll prefill → read → delete),
  `CsvUploadUser` (temp-upload → dispatch → poll pipeline; flow wall time
  recorded as a `FLOW` stats row).
- `backend/tests/performance/report_slow.py` — prints every (stage,
  endpoint) with p95 over a threshold (default 1000 ms) from the run CSVs.
- Backdrop seeding knobs on the existing COPY seeder
  (`app/seed/random_generator/`): `SEED_NUM_UNITS`, `SEED_NUM_USERS`,
  `SEED_YEARS`, `SEED_CEILING_SCALE` (per-type ceiling × scale, all
  VALIDATED, instead of the random ~67/module density).
  `seed_year_configuration` now also stamps provider TEST so `login-test`
  users see the seeded years. `seed_all` refuses non-local DB hosts unless
  `SEED_ALLOW_REMOTE=1` (backend/.env commonly points at the shared dev DB).
- `backend/Makefile` targets: `perf-csvs`, `perf-seed`, `perf-load`,
  `perf-sweep`, `perf-report`, `perf-db-dump`, `perf-db-restore`.

## How to run (local)

```bash
# one-time, with backend/.env DB_URL pointing at localhost
make run-db
cd backend
make db-migrate
make seed-data                      # locations, rooms, factors
make perf-seed                      # 600 units × 5 years × 0.1 ceiling ≈ 6M rows
make perf-csvs                      # upload CSVs from real factor data
make perf-db-dump                   # snapshot the expensive backdrop
uv run uvicorn app.main:app --workers 4 --port 8000

# then, per stage or the whole ladder
make perf-load PERF_USERS=50 PERF_CLASSES=ExplorerReadUser
make perf-sweep
make perf-report                    # endpoints with p95 > 1s
```

Reports land in `backend/tests/performance/reports/` (gitignored), one
CSV+HTML pair per stage. Restore the backdrop anytime with
`make perf-db-restore` instead of re-seeding.

Against dev: `make perf-load PERF_HOST=https://<dev-url>`; if `login-test`
is disabled there, export `PERF_AUTH_COOKIE=<auth_token JWT>`.

## Traps encoded in the locustfile (don't rediscover these)

- `RequestOriginMiddleware` 403s every cookie-authed non-GET without
  `Sec-Fetch-Site`/`Origin`; the client sends `Sec-Fetch-Site: none`.
- Auth is an httpOnly cookie, not a bearer token; `login-test` 302s and
  needs an exact `RoleName` value (`calco2.backoffice.admin` for global
  scope) — a wrong value yields a user with zero roles, not an error.
- Job/pipeline states are int enums (`state==3` finished, then check
  `result`; `2` = error). Poll `GET /v1/sync/pipelines/{id}`, never the
  SSE `/stream` routes.
- Trailing slashes are load-bearing on `carbon-reports/unit/...` and
  `project-plans/unit/...` routes (otherwise you measure 307s).

## Deliberate simplifications (ceilings for later)

- Backdrop emissions are the seeder's placeholders (`primary_factor_id`
  NULL): reads skip factor-join enrichment cost. The CSV-upload scenario
  exercises the real ingest+recalc path during the test, so the
  production-path cost is measured where it is heaviest. Upgrade path:
  run the recalc workflow over the backdrop, or raise
  `SEED_CEILING_SCALE` and accept the longer seed.
- All VUs of a role share one test user; per-unit-scoped users (role
  provider scopes) are not simulated.
- Default scale is 0.1 (≈6M rows). The full 600×5×21050 ≈ 63M is a knob
  away (`SEED_CEILING_SCALE=1`), not a code change.

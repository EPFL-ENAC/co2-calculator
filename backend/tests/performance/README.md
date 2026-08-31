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

Reports land here in `reports/` (gitignored): one `*_stats.csv` + `*.html`
per stage, `table_matrix.csv` for the matrix.

## What's in this folder

| File              | Purpose                                                                                                                                                                  |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `locustfile.py`   | The load scenarios: `ExplorerReadUser`, `ModuleReadUser`, `ExploreCreateUser`, `PlanUser`, `CsvUploadUser`                                                               |
| `table_matrix.py` | Exhaustive table-endpoint sweep: every submodule × limit {20,100,500,1000} × every sort column × order, plus filter search, deep pagination, item GETs, chart companions |
| `perf_common.py`  | Shared helpers (JWT minting, sort-column discovery) — importable without locust                                                                                          |
| `report_slow.py`  | Scans stage CSVs for endpoints with p95 over a threshold                                                                                                                 |

## How auth works

Every virtual user is a **distinct seeded DEFAULT-provider user**:
`make perf-load` derives `reports/perf_users.txt` from the DB and each VU
mints its own `auth_token` (same `JWT_HMAC_KEY` as the target). Principal
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

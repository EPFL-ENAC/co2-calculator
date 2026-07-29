---
name: verify
description: Launch and drive the CO2 calculator full stack (FastAPI + Quasar) locally to verify a change end-to-end with a test login.
---

# Verify the CO2 calculator locally

## Launch

```bash
# DB must be up (docker postgres). Migrations:
cd backend && make db-migrate

# Backend (background):
cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# Frontend dev server (background, :9000; proxies /api/* -> :8000/* stripping /api):
cd frontend && npm run dev
```

OpenAPI is at `http://127.0.0.1:8000/openapi.json` (NOT /v1/openapi.json); routes are mounted under `/v1`.

## Auth (debug builds only)

`GET /v1/auth/login-test?role=<role>` sets auth cookies (302). Roles:
`calco2.user.standard` (own-scope), `calco2.user.principal` (unit-scope),
`calco2.backoffice.admin` (global — passes `require_unit_access` for ANY unit).

- curl: `curl -c cookies.txt ".../v1/auth/login-test?role=calco2.backoffice.admin"` then `-b cookies.txt`.
- Browser/Playwright: navigate to `http://localhost:9000/api/v1/auth/login-test?role=...` (cookies land on localhost:9000 via the proxy), then goto `/` — guards resolve the default workspace.

## Test-user workspace prerequisites (gotchas)

Test roles are scoped to fixture unit institutional_ids 13032–13035 which are
NOT in the dev DB, and `make seed-data` fails because the fixture
`institutional_code`s collide with real units. What works:

1. Insert one TEST-provider unit with `institutional_id='13032'` and a free
   code (e.g. '99932'), copying other fields from `TEST_UNITS` in
   `backend/app/providers/test_fixtures.py`.
2. Insert `YearConfiguration(year=2026, provider=UserProvider.TEST, is_started=True)`
   — `configured_years` in `/v1/session` filters by the user's provider.
3. Create the Calculator report or `GET /v1/workspace/{unit}/{year}/home` 404s
   and the frontend loops: `POST /v1/carbon-reports/ {"year":2026,"unit_id":<id>}`.

Then login-test principal lands on `/en/<id>-enac-it4r-test/2026/home`.

## Driving the GUI

Playwright is a frontend devDependency; scripts must run from `frontend/`
(module resolution). Don't use `waitForLoadState('networkidle')` — the dev
server's HMR socket keeps it from firing; use `waitForURL`/`domcontentloaded`.

## Cleanup

Delete any data created on REAL units (low ids are real dev data). The
TEST-provider unit/year rows are provider-isolated and invisible to real users.

# Performance Test Implementation Plan

## Current Status

Locust performance tests are running with 4 user role classes:

- `PrincipalUser` (co2.user.principal)
- `BackofficeUser` (co2.backoffice.metier)
- `SuperAdminUser` (co2.superadmin)
- `StandardUser` (co2.user.std)

## Remaining Issues to Address

### 403 Forbidden Errors (Permission Denied)

These endpoints require specific roles that may not be covered:

#### Audit Endpoints (SuperAdmin required)

- [ ] `GET /api/v1/audit/activity` - Requires superadmin permission
- [ ] `GET /api/v1/audit/stats` - Requires superadmin permission
- [ ] `GET /api/v1/audit/activity/{id}` - Requires superadmin permission
- [ ] `GET /api/v1/audit/export` - Requires superadmin permission

#### Backoffice Endpoints (BackofficeMetier required)

- [ ] `GET /api/v1/backoffice/units` - Requires backoffice permission
- [ ] `GET /api/v1/backoffice/unit/{id}` - Requires backoffice permission
- [ ] `GET /api/v1/backoffice/years` - Requires backoffice permission
- [ ] `GET /api/v1/backoffice/export-detailed` - Requires backoffice permission
- [ ] `GET /api/v1/backoffice/export` - Requires backoffice permission
- [ ] `GET /api/v1/backoffice-reporting/units` - Requires backoffice permission

#### Files Endpoints (Backoffice required)

- [ ] `GET /api/v1/files/` - Requires backoffice permission

#### Sync Endpoints (SuperAdmin required)

- [ ] `POST /api/v1/sync/data-entries/{id}` - Requires superadmin permission
- [ ] `POST /api/v1/sync/factors/{module}/{factor}` - Requires superadmin permission
- [ ] `GET /api/v1/sync/jobs/by-status` - Requires backoffice/superadmin permission
- [ ] `GET /api/v1/sync/jobs/stream` - Requires backoffice/superadmin permission

#### Module Stats Endpoints (Principal/SuperAdmin required)

- [ ] `GET /api/v1/modules-stats/{unit}/{year}/{module}/stats` - Requires appropriate scope
- [ ] `GET /api/v1/modules/{unit}/evolution-over-time` - Requires appropriate scope
- [ ] `GET /api/v1/modules/{unit}/{year}/{module}` - Requires appropriate scope
- [ ] `GET /api/v1/modules/{unit}/{year}/{module}/stats-by-class` - Requires appropriate scope

### 422 Unprocessable Entity Errors (Validation/Parameter Issues)

These endpoints are failing due to missing or invalid parameters:

#### Factors Endpoints

- [ ] `GET /api/v1/factors/{data_entry_type}/class-subclass-map`
  - Issue: `data_entry_type` parameter needs valid value (e.g., "headcount", "electricity")
  - Fix: Use valid data entry type names from taxonomies

#### Taxonomies Endpoints

- [ ] `GET /api/v1/taxonomies/module_type/{module_type}`
  - Issue: `module_type` parameter needs valid value
  - Fix: Use valid module type names (e.g., "headcount", "professional_travel", "equipment", "surface")

- [ ] `GET /api/v1/taxonomies/data_entry_type/{data_entry_type}`
  - Issue: `data_entry_type` parameter needs valid value
  - Fix: Use valid data entry type names

#### Locations Endpoints

- [ ] `GET /api/v1/locations/search`
  - Issue: Missing required query parameters (e.g., `q`, `unit_id`)
  - Fix: Add required search parameters

- [ ] `GET /api/v1/locations/calculate-distance`
  - Issue: Missing required query parameters (e.g., `origin`, `destination`)
  - Fix: Add required distance calculation parameters

#### Units Endpoints

- [ ] `GET /api/v1/units/{unit_id}` - Returns 404
  - Issue: Endpoint may not exist or unit_id doesn't exist in DB
  - Fix: Verify endpoint exists in router, use valid unit_id

#### Carbon Reports Endpoints

- [ ] `POST /api/v1/carbon-reports/` - Returns 500
  - Issue: Server error during creation
  - Fix: Check payload schema, verify required fields, check backend logs

## Action Items

### Priority 1: Fix 422 Errors (Parameter Validation)

1. Update taxonomy endpoints with valid module_type and data_entry_type values
2. Update factors endpoints with valid data_entry_type values
3. Add required query parameters to locations endpoints
4. Fix carbon report creation payload

### Priority 2: Fix 403 Errors (Permission Coverage)

1. Verify role assignments in locustfile match actual permission requirements
2. Check if additional roles need to be tested (e.g., combinations)
3. Verify test database has appropriate data for each role's scope
4. Review OPA policy definitions to ensure test roles have expected permissions

### Priority 3: Fix 404 Errors (Missing Endpoints)

1. Verify `/api/v1/units/{unit_id}` endpoint exists
2. Use valid IDs that exist in test database

## Next Steps

1. Run `make perf-test` and capture current error summary
2. Fix 422 errors by updating parameter values in locustfile
3. Review OPA policies to understand exact permission requirements
4. Adjust user role assignments or add missing role combinations
5. Re-run tests and verify error reduction

## Test Commands

```bash
# Run performance test with web UI
make perf-test

# Run headless mode with specific user distribution
uv run locust -f tests/performance/locustfile.py \
  --headless \
  --users 10 \
  --spawn-rate 1 \
  --run-time 5m \
  --host=http://localhost:8000

# Run with custom user distribution
uv run locust -f tests/performance/locustfile.py \
  --headless \
  --users 20 \
  --spawn-rate 2 \
  --run-time 10m \
  --host=http://localhost:8000
```

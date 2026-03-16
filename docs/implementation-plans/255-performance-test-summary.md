# Performance Test Implementation Plan

## Current Status

Locust performance tests are running with 4 user role classes:

- `PrincipalUser` (co2.user.principal)
- `BackofficeUser` (co2.backoffice.metier)
- `SuperAdminUser` (co2.superadmin)
- `StandardUser` (co2.user.std)

## Latest Test Results Summary

### Total Failures: 171 requests across 27 endpoints

| Error Type                | Count | Endpoints Affected |
| ------------------------- | ----- | ------------------ |
| 403 Forbidden             | 141   | 19 endpoints       |
| 422 Unprocessable Entity  | 26    | 5 endpoints        |
| 404 Not Found             | 9     | 1 endpoint         |
| 500 Internal Server Error | 2     | 1 endpoint         |

### Failure Breakdown by Endpoint

| Endpoint                                           | Method | Failures | Error |
| -------------------------------------------------- | ------ | -------- | ----- |
| GET /audit/activity                                | GET    | 13       | 403   |
| GET /audit/stats                                   | GET    | 7        | 403   |
| GET /audit/export                                  | GET    | 6        | 403   |
| GET /audit/activity/{id}                           | GET    | 1        | 403   |
| GET /backoffice/units                              | GET    | 13       | 403   |
| GET /backoffice/unit/{id}                          | GET    | 12       | 403   |
| GET /backoffice-reporting/units                    | GET    | 12       | 403   |
| GET /backoffice/years                              | GET    | 7        | 403   |
| GET /backoffice/export                             | GET    | 4        | 403   |
| GET /backoffice/export-detailed                    | GET    | 4        | 403   |
| GET /files/                                        | GET    | 15       | 403   |
| GET /sync/jobs/by-status                           | GET    | 10       | 403   |
| GET /sync/jobs/stream                              | GET    | 3        | 403   |
| POST /sync/data-entries/{id}                       | POST   | 7        | 403   |
| POST /sync/factors/{module}/{factor}               | POST   | 2        | 403   |
| GET /modules/{unit}/{year}/{module}                | GET    | 15       | 403   |
| GET /modules/{unit}/{year}/{module}/stats-by-class | GET    | 9        | 403   |
| GET /modules/{unit}/evolution-over-time            | GET    | 7        | 403   |
| GET /modules-stats/{unit}/{year}/{module}/stats    | GET    | 13       | 403   |
| GET /taxonomies/module/{module}                    | GET    | 5        | 403   |
| GET /factors/{type}/class-subclass-map             | GET    | 11       | 422   |
| GET /taxonomies/module_type/{type}                 | GET    | 13       | 422   |
| GET /taxonomies/data_entry_type/{type}             | GET    | 3        | 422   |
| GET /locations/search                              | GET    | 7        | 422   |
| GET /locations/calculate-distance                  | GET    | 8        | 422   |
| GET /units/{id}                                    | GET    | 9        | 404   |
| POST /carbon-reports/                              | POST   | 2        | 500   |

## Remaining Issues to Address

### 403 Forbidden Errors (Permission Denied) - 141 failures

These endpoints require specific roles that may not be covered:

#### Audit Endpoints (SuperAdmin required) - 27 failures

- [ ] `GET /api/v1/audit/activity` - 13 failures
- [ ] `GET /api/v1/audit/stats` - 7 failures
- [ ] `GET /api/v1/audit/export` - 6 failures
- [ ] `GET /api/v1/audit/activity/{id}` - 1 failure

#### Backoffice Endpoints (BackofficeMetier required) - 50 failures

- [ ] `GET /api/v1/backoffice/units` - 13 failures
- [ ] `GET /api/v1/backoffice/unit/{id}` - 12 failures
- [ ] `GET /api/v1/backoffice-reporting/units` - 12 failures
- [ ] `GET /api/v1/backoffice/years` - 7 failures
- [ ] `GET /api/v1/backoffice/export` - 4 failures
- [ ] `GET /api/v1/backoffice/export-detailed` - 4 failures

#### Files Endpoints (Backoffice required) - 15 failures

- [ ] `GET /api/v1/files/` - 15 failures

#### Sync Endpoints (SuperAdmin/Backoffice required) - 22 failures

- [ ] `GET /api/v1/sync/jobs/by-status` - 10 failures
- [ ] `POST /api/v1/sync/data-entries/{id}` - 7 failures
- [ ] `GET /api/v1/sync/jobs/stream` - 3 failures
- [ ] `POST /api/v1/sync/factors/{module}/{factor}` - 2 failures

#### Module Endpoints (Principal/SuperAdmin scope issue) - 44 failures

- [ ] `GET /api/v1/modules/{unit}/{year}/{module}` - 15 failures
- [ ] `GET /api/v1/modules-stats/{unit}/{year}/{module}/stats` - 13 failures
- [ ] `GET /api/v1/modules/{unit}/{year}/{module}/stats-by-class` - 9 failures
- [ ] `GET /api/v1/modules/{unit}/evolution-over-time` - 7 failures

#### Taxonomy Endpoints (Scope/Permission issue) - 5 failures

- [ ] `GET /api/v1/taxonomies/module/{module}` - 5 failures

### 422 Unprocessable Entity Errors (Validation/Parameter Issues) - 42 failures

These endpoints are failing due to missing or invalid parameters:

#### Factors Endpoints - 11 failures

- [ ] `GET /api/v1/factors/{data_entry_type}/class-subclass-map`
  - Issue: `data_entry_type` parameter needs valid value (e.g., "headcount", "electricity")
  - Fix: Use valid data entry type names from taxonomies

#### Taxonomies Endpoints - 16 failures

- [ ] `GET /api/v1/taxonomies/module_type/{module_type}` - 13 failures
  - Issue: `module_type` parameter needs valid value
  - Fix: Use valid module type names (e.g., "headcount", "professional_travel", "equipment", "surface")

- [ ] `GET /api/v1/taxonomies/data_entry_type/{data_entry_type}` - 3 failures
  - Issue: `data_entry_type` parameter needs valid value
  - Fix: Use valid data entry type names

#### Locations Endpoints - 15 failures

- [ ] `GET /api/v1/locations/search` - 7 failures
  - Issue: Missing required query parameters (e.g., `q`, `unit_id`)
  - Fix: Add required search parameters

- [ ] `GET /api/v1/locations/calculate-distance` - 8 failures
  - Issue: Missing required query parameters (e.g., `origin`, `destination`)
  - Fix: Add required distance calculation parameters

### 404 Not Found Errors - 9 failures

- [ ] `GET /api/v1/units/{unit_id}` - 9 failures
  - Issue: Endpoint may not exist or unit_id doesn't exist in DB
  - Fix: Verify endpoint exists in router, use valid unit_id

### 500 Internal Server Error - 2 failures

- [ ] `POST /api/v1/carbon-reports/` - 2 failures
  - Issue: Server error during creation
  - Fix: Check payload schema, verify required fields, check backend logs

## Action Items

### Priority 1: Fix 422 Errors (Parameter Validation) - 42 failures

1. Update taxonomy endpoints with valid module_type and data_entry_type values
2. Update factors endpoints with valid data_entry_type values
3. Add required query parameters to locations endpoints
4. Fix carbon report creation payload

### Priority 2: Fix 403 Errors (Permission Coverage) - 141 failures

1. Verify role assignments in locustfile match actual permission requirements
2. Check if additional roles need to be tested (e.g., combinations)
3. Verify test database has appropriate data for each role's scope
4. Review OPA policy definitions to ensure test roles have expected permissions
5. **Key finding**: Module endpoints failing for PrincipalUser - may need scope adjustment
6. **Key finding**: Taxonomy/module endpoint failing - may need specific permission

### Priority 3: Fix 404/500 Errors - 11 failures

1. Verify `/api/v1/units/{unit_id}` endpoint exists in router
2. Use valid IDs that exist in test database
3. Investigate carbon report creation 500 error - check backend logs

## Next Steps

1. Fix 422 errors by updating parameter values in locustfile (quick win)
2. Review OPA policies to understand exact permission requirements for failing endpoints
3. Adjust user role assignments or add missing role combinations
4. Add missing endpoint `/api/v1/units/{unit_id}` if it doesn't exist
5. Investigate carbon report creation error
6. Re-run tests and verify error reduction

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

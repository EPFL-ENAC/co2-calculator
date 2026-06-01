# Bot Review TODOs: PR #1021

## Source Branch: `fix/310c-factors-stale-permission`

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR closes a privilege gap on the operator-facing stale-factors endpoint by aligning its authorization with the existing backoffice data-management routes.

**Changes:**

- Replace `Depends(get_current_user)` on `GET /v1/factors/stale` with `Depends(require_permission("backoffice.data_management", "view"))`.
- Document the required permission on the route itself for API consumers and maintainers.
- Add Postgres-backed integration coverage for both denied (`403`) and permitted (`200`) access to the endpoint.

### Reviewed changes

Copilot reviewed 2 out of 2 changed files in this pull request and generated no comments.

| File                                                                                  | Description                                                                                                                                 |
| ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/app/api/v1/factors.py`                                                       | Tightens the `/stale` endpoint to use the established backoffice permission gate and updates the route docstring.                           |
| `backend/tests/integration/services/data_ingestion/test_factors_stale_endpoint_pg.py` | Adds end-to-end permission-gate tests to verify unauthorized users are denied and authorized users still get the expected empty-list shape. |

---

## Action Items

_No substantive items — Copilot generated no inline comments and approved the change._

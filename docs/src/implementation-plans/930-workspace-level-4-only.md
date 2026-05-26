---
status: delivered
issue: 930
last_updated: 2026-05-22
title: "Workspace shows only level-4 units"
summary: "Backend /users/units endpoint hardcodes level == 4 so workspace only ever sees actual lab-level units, not EPFL or affiliation-level ancestors."
---

## Problem

The workspace unit picker currently surfaces ancestors of the user's lab — "EPFL" (level 1), faculties / services centraux (level 2), and instituts (level 3) — alongside the actual labs (level 4) where CO₂ data is recorded. This dilutes the picker and lets users select scopes that have no own data (only aggregated children).

Expected behavior: `/users/units` returns **only level-4 units** — the leaves of the ACCRED hierarchy, i.e. the actual labs/units. No "EPFL", no faculty, no institute.

Originally reported in [#855](https://github.com/epfl-eco/co2-calculator/issues/855), tracked here as [#930](https://github.com/epfl-eco/co2-calculator/issues/930).

## Decision applied

Backend filter — **hardcode `level == 4`** in `/users/units` (mirrors the `backoffice_reporting.py` /affiliations precedent that hardcodes `level IN (2, 3)`). Frontend remains thin.

Rationale:

- Backend is the source of truth (memory rule).
- Precedent for hardcoding a level discriminator already exists at `backend/app/api/v1/backoffice_reporting.py:44`.
- Frontend has only one consumer (`frontend/src/stores/workspace.ts:224`), and it does no level-aware logic — adding a query param would just push policy decisions into the client.

## Files to change

| File                                               | Function / lines                                          | Change                                                                                           |
| -------------------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `backend/app/services/unit_service.py`             | `get_user_units()` (line 57, query built at lines 99-124) | Add `.where(col(Unit.level) == 4)` to the `query` before the policy-filter block (~ line 113).   |
| `backend/tests/unit/services/test_unit_service.py` | new test cases                                            | Cover: mixed-level user roles → only level-4 returned; user with only level-3 role → empty list. |
| `backend/tests/integration/v1/`                    | new file `test_users_units_level_filter.py`               | Integration smoke that hits `/api/v1/users/units` with a fixture user having mixed-level roles.  |

Optional / **recommended NO**:

- `backend/app/api/v1/users.py` (lines 29-57): do **not** add a `level` query param. Decision keeps the rule on the server.
- `backend/app/schemas/unit.py` (`UnitWithUserRole`, lines 10-34): do **not** expose `level` to the frontend; nothing on the FE needs it now (filtering is server-side).

## Approach

1. **Add the level filter.** In `backend/app/services/unit_service.py::get_user_units()`, after the `.where(col(UnitUser.user_id) == user.id)` clause (line 112), add:

   ```python
   query = query.where(col(Unit.level) == 4)
   ```

   Use `col()` per the repo convention (mypy `ColumnElement`).

2. **Confirm fixtures cover mixed levels.** `backend/app/providers/test_fixtures.py:74-97` already includes level-3 and level-4 test units. Verify the fixture user holds `UnitUser` rows pointing at both levels; if not, add a level-3 `UnitUser` row so the regression test has something to filter out.

3. **Add unit tests on `UnitService.get_user_units()`** asserting the filter (mixed-level user → response excludes non-level-4).

4. **Add an integration test** hitting `/api/v1/users/units` end-to-end against the test DB, asserting `level` of every returned row is 4 (after re-fetching by id, since the response schema does not expose `level`).

5. **No frontend change.** `frontend/src/stores/workspace.ts:224` (`api.get('users/units')`) and `LabSelectorItem.vue` render whatever the API returns. Confirmed via `grep -rn "users/units" frontend/src/` — single consumer.

## Tests

Proposed test functions (all new):

- `tests/unit/services/test_unit_service.py`
  - `test_get_user_units_returns_only_level_4_when_user_has_mixed_level_roles`
  - `test_get_user_units_returns_empty_when_user_only_has_non_level_4_roles`
  - `test_get_user_units_unchanged_for_user_with_only_level_4_roles` (no-regression)

- `tests/integration/v1/test_users_units_level_filter.py`
  - `test_users_units_endpoint_filters_to_level_4`

## Verification

```bash
cd backend
uv run pytest tests/integration/v1/test_users_units_level_filter.py -xvs
uv run pytest tests/unit/services/test_unit_service.py -xvs
make backend-dev
# log in as a user with mixed-level roles in dev DB; curl /api/v1/users/units; verify only level-4 entries
cd ../frontend
bun run lint && bun run typecheck    # should be no-op (no FE change)
# Manual: bun run dev → workspace setup page → verify dropdown shows only labs (no "EPFL", no faculties)
```

## Resolved questions

1. **Is `level == 4` the right discriminator for ALL providers?** Kept as `level == 4` in delivery. ACCRED is the only provider today and returns levels 1-4 (`backend/app/providers/unit_provider.py:180-218`); this also matches the existing `backoffice_reporting.py:44` precedent (`level IN (2, 3)`). When a second provider lands, revisit with leaf semantics (`Unit.children == None` via self-join or an `is_leaf` column) or a provider-scoped `leaf_level` config. The comment on the new `.where()` clause documents the assumption inline.

2. **Does any other endpoint or frontend code rely on `/users/units` returning higher-level units?**
   - Frontend: single consumer at `frontend/src/stores/workspace.ts:224` — only renders `name`, `affiliations`, `current_user_role`, no level-aware branching. No regression.
   - Backend: `UnitService.get_user_units()` is also reached via `GET /api/v1/units` (`backend/app/api/v1/units.py:44`). That endpoint has **no frontend consumer** (`grep -rn "'units'" frontend/src/` returns no `api.get('units')` call — only `api.get('users/units')` and `api.get('units/{id}')`). Filtering both endpoints to level-4 is therefore safe and consistent with the workspace semantic the rule encodes.

3. **Should the response schema expose `level` for any UI affordance?** No. Filter stays server-side; `UnitWithUserRole` unchanged.

## Delivery notes

- Code change: 3 lines (1 `.where()` + 2-line intent comment) at `backend/app/services/unit_service.py:113-115`.
- Unit tests: 3 new tests in `backend/tests/unit/services/test_unit_service.py::TestGetUserUnitsLevelFilter` (mixed levels, only-non-4 → empty, only-4 baseline).
- Integration test: `backend/tests/integration/v1/test_users_units_level_filter.py` — hits `GET /api/v1/users/units` with the real test DB session via FastAPI dependency override.
- mypy clean; full backend suite (1478 tests) passes.

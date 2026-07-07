---
status: proposed
issue: 1204
last_updated: 2026-07-07
title: "Restrict backoffice year creation to [2025, current_year]"
summary: "Cap the backoffice year selector and year-creation endpoint to years from 2025 through the current year, removing the leftover 2023/2024 test range."
---

# Restrict backoffice year creation to [2025, current_year]

## Problem

The backoffice year selector on `DataManagementPage.vue` currently offers years from 2023 through the current year. That range was a testing convenience — real operation starts at 2025. Per #1204 / #1403 acceptance criteria, only years `2025 <= year <= current_year` should be creatable (today: 2025 and 2026).

The frontend range is also the _only_ gate: `POST /year-configuration/{year}` accepts any integer `year` with no bounds check, so a stale tab, direct API call, or future UI regression can still create a 2023/2024 config. Per project convention the backend must be the source of truth for this validation, not just the dropdown.

## Design

**Validation point (frontend, UI restriction only):**
`frontend/src/stores/yearConfig.ts:187` — `const MIN_YEAR = 2023;` drives `availableYears`, which is consumed by a single QSelect on `DataManagementPage.vue:287` (`options="availableYears"`) used both to pick an existing year to manage and, via the same `selectedYear` ref, to create a new one (`DataManagementPage.vue:177`, `yearConfigStore.createConfig(selectedYear.value)`). Bumping `MIN_YEAR` to `2025` fixes the dropdown for both flows in one edit.

**Validation point (backend, actual enforcement):**
`backend/app/api/v1/year_configuration.py:608` — `create_year_configuration(year: int, ...)` has no range check before the duplicate-existence query at line 634. Add a bounds check immediately after the permission check (before the `SELECT` at line 634): reject with `400` if `year < MIN_CONFIGURABLE_YEAR` or `year > datetime.now().year`.

New constant `MIN_CONFIGURABLE_YEAR = 2025` goes in `backend/app/core/constants.py` (alongside the other bare int constants like `MIN_PAGE_SIZE`), imported into `year_configuration.py`. No shared frontend/backend constants module exists in this codebase — duplicating the literal `2025` in the TS store is consistent with existing precedent (no cross-language constant sharing elsewhere).

Out of scope: any 2023/2024 `YearConfiguration` rows already persisted in a live DB are not touched — the issue only bounds _creatable_ years going forward, not historical cleanup.

## Steps

- [ ] Backend: add `MIN_CONFIGURABLE_YEAR = 2025` to `backend/app/core/constants.py`.
- [ ] Backend: in `create_year_configuration` (`backend/app/api/v1/year_configuration.py:608`), after the `is_permitted` check and before the existing-config query, raise `HTTPException(400, ...)` if `year < MIN_CONFIGURABLE_YEAR or year > datetime.now().year`.
- [ ] Backend: add a regression test asserting `POST /year-configuration/2024` returns 400 and `POST /year-configuration/2025` still succeeds.
- [ ] Frontend: change `frontend/src/stores/yearConfig.ts:187` from `const MIN_YEAR = 2023;` to `const MIN_YEAR = 2025;`; drop the stale `// TODO: fix the available years dynamically...` comment only if this change fully resolves it, otherwise leave as-is (dynamic-from-`configuredYears` is a separate concern).
- [ ] Verify: reload `DataManagementPage.vue` year dropdown shows only 2025/2026 (for 2026-07-07), and creating 2024 via direct API call (curl/Postman) returns 400.

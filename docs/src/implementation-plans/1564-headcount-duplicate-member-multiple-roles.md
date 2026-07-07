---
status: proposed
issue: 1564
last_updated: 2026-07-07
title: "Headcount: Allow the Same Member With Multiple Roles in One Unit"
summary: "Headcount uniqueness is keyed on user_institutional_id alone, so a member with two SIUS roles in the same unit gets their second CSV row silently dropped."
---

# Headcount: Allow the Same Member With Multiple Roles in One Unit

## Problem

`docs/src/implementation-plans/518-headcount-uniqueness-validation.md` (delivered) scoped headcount uniqueness to "same SCIPER within the same `carbon_report_module_id`" (unit + year) and shipped it keyed on `user_institutional_id` alone. That design didn't account for `sius_code` (the member's function/role, one of `HeadcountItemResponse.SIUS_CODE_VALUES` in `backend/app/modules/headcount/schemas.py:29`) — a real person can legitimately hold two roles in the same unit and appear as two headcount rows: same `unit_institutional_id` + `user_institutional_id`, different `sius_code`/`fte`.

The single-field check landed in two places, both routing through the same shared primitive, `DataEntryRepository.check_json_field_unique` (`backend/app/repositories/data_entry_repo.py:252-284`), via `DataEntryService.check_institutional_id_unique` (`backend/app/services/data_entry_service.py:66-76`, hardcoded `field="user_institutional_id"`):

1. **Manual create (API)** — `backend/app/workflows/carbon_report_module.py:68-83`. A second role for the same SCIPER raises `HTTPException(422, "DUPLICATE_INSTITUTIONAL_ID")`.
2. **Bulk/backoffice CSV ingestion** — `backend/app/services/data_ingestion/base_csv_provider.py:982-1009`. This is the path the issue actually hits: rows are processed in order, an in-batch `seen_institutional_ids: dict[module_id, set[uid]]` is checked first (line 992-998), then the DB check (line 999-1002). Either hit records `stats["errors"]` with `"DUPLICATE_INSTITUTIONAL_ID"` and `continue`s — the second role's row is silently skipped, matching the issue report exactly ("the second time the same user_institutional_id appears the row is ignored").

Both enforcement points treat `user_institutional_id` as the whole uniqueness key; neither considers `sius_code`.

## Design

Fix once, at the shared primitive, not in each caller:

- **`DataEntryService.check_institutional_id_unique`** (`data_entry_service.py:66-76`): extend to take the composite key. Simplest shape: add a required `sius_code: str` param and have it call `repo.check_json_field_unique` twice-filtered — or, cleaner, extend `DataEntryRepository.check_json_field_unique` to accept a `fields: dict[str, str]` (multiple `DataEntry.data[k].as_string() == v` predicates ANDed) instead of a single `field`/`value` pair, matching the existing JSON-query pattern already used in `filter_map`/`sort_map`. Rename the wrapper to `check_member_role_unique` (or similar) to reflect the new key; update its two call sites.
- **`backend/app/workflows/carbon_report_module.py:68-83`**: pass `sius_code` from `validated_data` alongside `uid` into the renamed check.
- **`backend/app/services/data_ingestion/base_csv_provider.py:982-1009`**: change `seen_institutional_ids` from `dict[int, set[str]]` (uid) to `dict[int, set[tuple[str, str]]]` (uid, sius_code), and pass `sius_code` into the DB-level check call. `HeadCountCreate.sius_code` (`backend/app/modules/headcount/schemas.py:46`) is a required field on member rows, so it's always present by the time this check runs.
- **Advisory `GET .../check-unique` endpoint** (`backend/app/api/v1/carbon_report_module.py:750-812`, backed by `DataEntryService.check_json_field_unique`): currently single-field only, generic (not headcount-specific). Grep of `frontend/src` found no live caller (only present in generated `frontend/src/types/api/openapi.d.ts`) — it's currently dead frontend-side. Leave the generic single-field signature as-is (it's not the headcount-specific path); do not wire a composite variant into it unless a future member-form pre-submit check is actually built.
- **Downstream aggregation**: `aggregate_by="sius_code"` (`backend/app/api/v1/carbon_report_module.py:299`, FTE-per-function stats) already groups by function and sums `fte` per `DataEntry` row — one row per role is the correct unit of aggregation there, so multiple rows per person need no change. Checked `DataEntryRepository` for any `SELECT DISTINCT` / dedup on `user_institutional_id` in stats/count paths (`data_entry_repo.py`) — none found, so no existing KPI silently double-counts or under-counts people today. Note only: any future "distinct headcount" (people, not roles) metric must `DISTINCT` on `user_institutional_id`, not just count rows.

No DB schema change needed — `DataEntry.data` is JSON, the uniqueness key is enforced at the application layer only (same as #518), so this is a pure application-level composite-key fix.

## Steps

- [ ] Extend `DataEntryRepository.check_json_field_unique` (`data_entry_repo.py:252`) to accept a `fields: dict[str, str]` composite predicate (backward-compatible: single-entry dict == today's behavior), or add a sibling method — reuse the existing `DataEntry.data[k].as_string()` pattern.
- [ ] Update `DataEntryService.check_institutional_id_unique` (`data_entry_service.py:66`) to require `sius_code` and check the composite `(user_institutional_id, sius_code)` key; rename to reflect the new semantics.
- [ ] Update `backend/app/workflows/carbon_report_module.py:68-83` to pass `sius_code` into the renamed check.
- [ ] Update `backend/app/services/data_ingestion/base_csv_provider.py:982-1009`: key `seen_institutional_ids` by `(uid, sius_code)` tuple; pass `sius_code` into the DB check.
- [ ] Regression test: CSV batch with two rows, same `unit_institutional_id` + `user_institutional_id`, different `sius_code` -> both rows ingested, `stats["errors"]` empty for those rows.
- [ ] Regression test: CSV batch with two rows, same `unit_institutional_id` + `user_institutional_id` + same `sius_code` (true duplicate) -> second row still rejected with `DUPLICATE_INSTITUTIONAL_ID`.
- [ ] Regression test: manual API create of a second role for an existing member (same unit, same SCIPER, different `sius_code`) -> 201, not 422.
- [ ] Update `docs/src/implementation-plans/518-headcount-uniqueness-validation.md` status/scope note to point at this plan (the "uniqueness is per `carbon_report_module_id`" line needs a "...and per `sius_code`" amendment) per the "keep implementation plans aligned" convention.

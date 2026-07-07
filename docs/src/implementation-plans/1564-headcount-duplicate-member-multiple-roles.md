---
status: proposed
issue: 1564
last_updated: 2026-07-07
title: "Headcount: Allow the Same Member With Multiple Roles in One Unit"
summary: "Headcount uniqueness is keyed on user_institutional_id alone, so a member with two SIUS roles in the same unit gets their second CSV row silently dropped; fixing that exposes a real duplicate-row risk in the Professional Travel <-> Headcount join that must be fixed in the same PR."
---

# Headcount: Allow the Same Member With Multiple Roles in One Unit

## Problem

`docs/src/implementation-plans/518-headcount-uniqueness-validation.md` (delivered) scoped headcount uniqueness to "same SCIPER within the same `carbon_report_module_id`" (unit + year) and shipped it keyed on `user_institutional_id` alone. That design didn't account for `sius_code` (the member's function/role, one of `HeadcountItemResponse.SIUS_CODE_VALUES` in `backend/app/modules/headcount/schemas.py:29`) — a real person can legitimately hold two roles in the same unit and appear as two headcount rows: same `unit_institutional_id` + `user_institutional_id`, different `sius_code`/`fte`.

The single-field check landed in two places, both routing through the same shared primitive, `DataEntryRepository.check_json_field_unique` (`backend/app/repositories/data_entry_repo.py:252-284`), via `DataEntryService.check_institutional_id_unique` (`backend/app/services/data_entry_service.py:66-76`, hardcoded `field="user_institutional_id"`):

1. **Manual create (API)** — `backend/app/workflows/carbon_report_module.py:68-83`. A second role for the same SCIPER raises `HTTPException(422, "DUPLICATE_INSTITUTIONAL_ID")`.
2. **Bulk/backoffice CSV ingestion** — `backend/app/services/data_ingestion/base_csv_provider.py:982-1009`. This is the path the issue actually hits: rows are processed in order, an in-batch `seen_institutional_ids: dict[module_id, set[uid]]` is checked first (line 992-998), then the DB check (line 999-1002). Either hit records `stats["errors"]` with `"DUPLICATE_INSTITUTIONAL_ID"` and `continue`s — the second role's row is silently skipped, matching the issue report exactly ("the second time the same user_institutional_id appears the row is ignored").

Both enforcement points treat `user_institutional_id` as the whole uniqueness key; neither considers `sius_code`.

**Confirmed by the reporter (2026-07-07), with real data shape:**

Same-unit, two roles — the case this issue is about, currently broken (second row dropped):

```
unit_institutional_id  name     sius_code  user_institutional_id  fte
1234                   XXX XXX  53         123456                 0.75
1234                   XXX XXX  54         123456                 0.25
```

Both rows must be accepted and shown in the headcount module, each contributing its own FTE to the SIUS-code chart independently.

Cross-unit, same role — a _different_ shape, already working correctly today (uniqueness is scoped per `carbon_report_module_id`, i.e. per unit+year, so two different units never collide):

```
unit_institutional_id  name     sius_code  user_institutional_id  fte
1234                   XXX XXX  53         123456                 0.75
5678                   XXX XXX  53         123456                 0.25
```

This second shape is **not** part of this bug and needs no uniqueness-key change — it's confirmation that the existing per-unit scoping already does the right thing. It matters below only because it's the same "one SCIPER, multiple headcount rows" precondition that the Professional Travel join has to tolerate — and, cross-unit, it already does (a travel entry only ever joins against its own unit's headcount roster, so a same-SCIPER row in a _different_ unit is never a join candidate). The genuinely new risk is same-unit, multi-role, which today can't exist in the data at all (rejected at ingestion) and will start existing the moment this fix ships.

## Design

Fix once, at the shared primitive, not in each caller:

- **`DataEntryService.check_institutional_id_unique`** (`data_entry_service.py:66-76`): extend to take the composite key. Simplest shape: add a required `sius_code: str` param and have it call `repo.check_json_field_unique` twice-filtered — or, cleaner, extend `DataEntryRepository.check_json_field_unique` to accept a `fields: dict[str, str]` (multiple `DataEntry.data[k].as_string() == v` predicates ANDed) instead of a single `field`/`value` pair, matching the existing JSON-query pattern already used in `filter_map`/`sort_map`. Rename the wrapper to `check_member_role_unique` (or similar) to reflect the new key; update its two call sites.
- **`backend/app/workflows/carbon_report_module.py:68-83`**: pass `sius_code` from `validated_data` alongside `uid` into the renamed check.
- **`backend/app/services/data_ingestion/base_csv_provider.py:982-1009`**: change `seen_institutional_ids` from `dict[int, set[str]]` (uid) to `dict[int, set[tuple[str, str]]]` (uid, sius_code), and pass `sius_code` into the DB-level check call. `HeadCountCreate.sius_code` (`backend/app/modules/headcount/schemas.py:46`) is a required field on member rows, so it's always present by the time this check runs.
- **Advisory `GET .../check-unique` endpoint** (`backend/app/api/v1/carbon_report_module.py:750-812`, backed by `DataEntryService.check_json_field_unique`): currently single-field only, generic (not headcount-specific). Grep of `frontend/src` found no live caller (only present in generated `frontend/src/types/api/openapi.d.ts`) — it's currently dead frontend-side. Leave the generic single-field signature as-is (it's not the headcount-specific path); do not wire a composite variant into it unless a future member-form pre-submit check is actually built.
- **Downstream aggregation**: `aggregate_by="sius_code"` (`backend/app/api/v1/carbon_report_module.py:299`, FTE-per-function stats) already groups by function and sums `fte` per `DataEntry` row — one row per role is the correct unit of aggregation there, so multiple rows per person need no change. Checked `DataEntryRepository` for any `SELECT DISTINCT` / dedup on `user_institutional_id` in stats/count paths (`data_entry_repo.py`) — none found, so no existing KPI silently double-counts or under-counts people today. Note only: any future "distinct headcount" (people, not roles) metric must `DISTINCT` on `user_institutional_id`, not just count rows.

No DB schema change needed — `DataEntry.data` is JSON, the uniqueness key is enforced at the application layer only (same as #518), so this is a pure application-level composite-key fix.

## Downstream impact: Professional Travel join must be fixed in the same PR

This is not optional follow-up work — shipping the composite-uniqueness fix alone, without this, introduces a live correctness bug in every unit that has a genuine multi-role member with travel data.

**The bug.** `DataEntryRepository`'s travel list/enrichment query (`backend/app/repositories/data_entry_repo.py:706-722`) joins every Professional Travel `DataEntry` to a headcount `MemberEntry` (an aliased `DataEntry`) purely to read the traveler's display name:

```python
statement = statement.join(
    MemberEntry,
    (
        MemberEntry.data["user_institutional_id"].as_string()
        == DataEntry.data["user_institutional_id"].as_string()
    )
    & (col(MemberEntry.carbon_report_module_id) == col(DataEntry.carbon_report_module_id))
    & (col(MemberEntry.data_entry_type_id) == DataEntryTypeEnum.member.value),
    isouter=True,
)
```

This assumes **exactly one** headcount row per `(user_institutional_id, carbon_report_module_id)` — true today only because the ingestion-side uniqueness check (the bug this plan fixes) has been silently enforcing it as a side effect. The moment a unit has a real two-role member (the confirmed same-unit case above), this join matches **two** `MemberEntry` rows for that SCIPER, and every one of that person's travel `DataEntry` rows gets duplicated in the result set — once per matching role. `traveler_name` itself won't visibly differ (the `name` field is identical on both role rows), so the duplication is invisible in that column, but list pagination and any `kg_co2eq` sum/rollup computed from these joined rows will double-count that person's trips. Confirmed there is no `LIMIT`/`DISTINCT`/dedup anywhere in this query path that would catch it — `count_stmt` (used for pagination totals) deliberately excludes the `MemberEntry` join already (`count_factor_joins` doesn't include it), which means **count and returned rows can already disagree in row count** once fan-out happens, on top of the double-counted emissions.

`professional_travel/schemas.py` confirms travel entries capture only `user_institutional_id` today — no `sius_code`/role field (there's a commented-out `traveler_id`/`traveler_name` pair suggesting an FK-based approach was considered and shelved). So travel currently has no way to say _which_ of a person's roles a given trip belongs to, even if we wanted it to.

**Two ways to fix it — need a decision before implementation, not a default:**

- **(A) Make travel role-aware.** Capture `sius_code` (or a direct FK to the specific headcount `DataEntry.id`) on the traveler selection in the frontend dropdown, store it on the travel entry, and extend the join predicate to match on it too — restores a 1:1 join. Correct if a trip is conceptually attributable to a specific role/function. Bigger surface: frontend traveler-picker UX (must show and let the user pick among a person's roles when they have more than one), a new field on travel create/update DTOs, a data migration question for existing travel rows (which role do they retroactively belong to — unanswerable from existing data, would need to default to "unknown"/first-match).
- **(B) Make the join deterministic instead of role-aware.** A trip belongs to the _person_, not a role — `traveler_name` is decorative lookup data, identical across that person's role rows anyway. Replace the plain `JOIN` with a `LEFT JOIN LATERAL ... LIMIT 1` (or the correlated-subquery equivalent already shipped in `docs/src/implementation-plans/1661-sql-factor-resolution.md` for the exact same "pick one deterministically instead of fanning out" problem) so multi-role members never produce duplicate travel rows, full stop. Smaller, self-contained, no frontend/DTO change, no migration question — but permanently forecloses ever attributing a specific trip to a specific role.

Recommendation: (B), on the same reasoning `1661-sql-factor-resolution.md` used — same codebase, same shape of problem, already-proven pattern, and nothing in the #1564 issue or the reporter's examples asks for role-specific trip attribution. Flagging as an open decision rather than assuming, since it's a product call, not just an implementation detail.

## Steps

- [ ] Extend `DataEntryRepository.check_json_field_unique` (`data_entry_repo.py:252`) to accept a `fields: dict[str, str]` composite predicate (backward-compatible: single-entry dict == today's behavior), or add a sibling method — reuse the existing `DataEntry.data[k].as_string()` pattern.
- [ ] Update `DataEntryService.check_institutional_id_unique` (`data_entry_service.py:66`) to require `sius_code` and check the composite `(user_institutional_id, sius_code)` key; rename to reflect the new semantics.
- [ ] Update `backend/app/workflows/carbon_report_module.py:68-83` to pass `sius_code` into the renamed check.
- [ ] Update `backend/app/services/data_ingestion/base_csv_provider.py:982-1009`: key `seen_institutional_ids` by `(uid, sius_code)` tuple; pass `sius_code` into the DB check.
- [ ] Regression test: CSV batch with two rows, same `unit_institutional_id` + `user_institutional_id`, different `sius_code` -> both rows ingested, `stats["errors"]` empty for those rows.
- [ ] Regression test: CSV batch with two rows, same `unit_institutional_id` + `user_institutional_id` + same `sius_code` (true duplicate) -> second row still rejected with `DUPLICATE_INSTITUTIONAL_ID`.
- [ ] Regression test: manual API create of a second role for an existing member (same unit, same SCIPER, different `sius_code`) -> 201, not 422.
- [ ] Update `docs/src/implementation-plans/518-headcount-uniqueness-validation.md` status/scope note to point at this plan (the "uniqueness is per `carbon_report_module_id`" line needs a "...and per `sius_code`" amendment) per the "keep implementation plans aligned" convention.
- [ ] **Decision needed before this step**: option (A) or (B) above for the Professional Travel join. Once decided:
  - [ ] (B, recommended) Replace the plain `MemberEntry` join in `data_entry_repo.py:706-722` with a `LEFT JOIN LATERAL ... LIMIT 1` (or correlated-subquery equivalent, matching `1661-sql-factor-resolution.md`'s pattern) keyed on `(user_institutional_id, carbon_report_module_id)`, deterministic tie-break (e.g. lowest `sius_code` or lowest `id`) when a person has multiple roles.
  - [ ] (A, alternative) Add role capture to travel create/update DTOs + frontend traveler picker, extend the join predicate to include it, and resolve the retroactive-migration question for existing travel rows.
- [ ] Regression test pinning the travel-join fix: seed a same-unit two-role member with at least one travel entry, assert the travel list returns exactly one row for that entry (not two) and `kg_co2eq` sums aren't doubled — this is the test that would have caught this bug, must ship in the same PR as the composite-uniqueness change, not as a follow-up.

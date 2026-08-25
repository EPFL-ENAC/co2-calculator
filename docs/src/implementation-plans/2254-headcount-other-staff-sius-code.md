---
status: delivered
issue: 2254
last_updated: 2026-08-25
title: "Headcount: members without a (known) SIUS code become Other staff (-1)"
summary: "The Tableau sync now delivers members without a SIUS code. Ingestion (API + CSV + create/update handler) normalizes empty/missing/unknown codes to the stored sentinel -1; -1 is a display-only 'Other staff/Autre personnel' function in the table and FTE chart, not offered in the manual dropdown. Existing DB rows are left untouched."
---

# Headcount: `sius_code` optional, "Other staff" sentinel `-1`

## Problem

The headcount Tableau API delivers a new category of members **without a SIUS
code**; the API path bypasses `HeadCountCreate` and stored them as
`sius_code: ""`, which rendered as a blank bar in the "FTE per function"
chart and a blank Function cell in the table. The spec change (#2254): SIUS
is no longer mandatory, and such rows — plus rows with an **unknown** code —
must display as "Other staff" / "Autre personnel".

## Design

**Normalize at ingestion, store the sentinel `-1`.** Every write path maps
empty/missing/unknown codes to `OTHER_SIUS_CODE = "-1"`; from there `-1`
behaves like any other code (stats GROUP BY key, unique index participant,
i18n label key), so no display-fallback logic is needed for new data.

- `backend/app/modules/headcount/data_entries.py` — `OTHER_SIUS_CODE = "-1"`
  and `normalize_sius_code()` (anything outside `SIUS_CODE_VALUES` → `-1`);
  `HeadCountCreate.sius_code` defaults to `-1` (this alone makes the CSV
  `sius_code` header optional, via `_get_required_columns_from_handler`);
  create/update validators accept the widened set.
- `backend/app/modules/headcount/handlers.py` — `validate_create` /
  `validate_update` normalize the **raw payload** before DTO construction.
  Persisted `data` carries the raw payload (`unflatten_payload` runs before
  field validators), so this is the only point where `-1` reaches storage
  for CSV upload and form/API create; update normalizes only when the field
  is present (partial-update semantics).
- `headcount_members_api_provider.py` — `transform_data` normalizes too (it
  builds `DataEntry` directly, bypassing the DTO). In-batch role dedup then
  collapses a person's blank+unknown roles into one `-1` row, and
  `uq_member_role_per_module` enforces one (person, Other staff) row per
  module — `-1` is a real value, unlike NULL (`NULLS DISTINCT`).
- `data_entry_repo.py` `get_headcount_fte_breakdown` — deterministic key
  order: codes ascending, `-1` last (dict order is the chart's bar order;
  the route appends `student` after).
- `simulator_plan_service.py` planner prefill — skips `-1` like it skipped
  missing codes: planner has no "Other staff" category (follow-up issue).

Frontend:

- `frontend/src/i18n/headcount_factor.ts` — `'-1'` → "Other staff" /
  "Autre personnel" (bare-code key, same pattern as `'51'`–`'59'`; chart
  resolves stats keys through `te(key) ? t(key) : key`, so it needs no code
  change).
- `frontend/src/constant/module-config/headcount.ts` — **`-1` is NOT a
  dropdown option** (user decision: not selectable in manual entry). Display
  goes through `optionLabelKey: '{value}'`: `renderCell`'s option lookup
  serves `51`–`59` as before, and the option-miss falls through to
  `$te('-1') ? $t('-1')` → "Other staff". Imported rows are policy-locked
  and always render via that read-only path.

## Explicitly out of scope

- **Existing DB rows** with `""`/missing/unknown codes are left as-is (user
  decision: "nothing" — no migration, no read-time fallback). They keep
  today's rendering until a re-sync rewrites them.
- Planner "Other staff" category (`modules_planner/headcount`).
- Martina's data-doc update (SIUS not mandatory) — her checklist item.

## Tests

- `tests/unit/modules/test_headcount_schemas.py` — `sius-missing` moved to
  the valid matrix (defaults `-1`); handler-normalization matrix (missing /
  None / `""` / whitespace / unknown `62` → `-1` in the persisted `data`,
  known codes preserved; update untouched when field absent).
- `test_headcount_members_api_provider.py` — blank/unknown SIUS captions
  kept as `-1`.
- `test_base_csv_provider.py` — `sius_code` no longer a required CSV column
  for the real headcount handler; two `-1` roles for one person dedupe.
- `test_data_entry_repo.py` — breakdown key order pins `-1` last with
  summed FTE.

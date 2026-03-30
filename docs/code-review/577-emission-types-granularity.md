# Code Review: feat/577-featcharts-emissions-types-granularity-updated

**Branch:** `feat/577-featcharts-emissions-types-granularity-updated`
**Date:** 2026-03-25
**Reviewer:** Claude
**Latest commit:** `abadc872f` — feat: enhance emission types and granularity for buildings and additional purchases

---

## Summary

This branch adds a 4th hierarchy level (8-digit WW codes) to `EmissionType` for room-type granularity in buildings (office, laboratories, archives, libraries, auditoriums, miscellaneous), fuel-type granularity for combustion, and an `ln2` subcategory for additional purchases. It also refactors chart keys from display strings to snake_case identifiers, aligning frontend and backend naming.

---

## Findings

### 1. LOW — Numbering scheme note

**File:** `backend/app/models/data_entry_emission.py`

The WW-level values (e.g. `6010101`) are 8-digit codes (`06 01 01 01`) with the leading zero dropped by Python's int representation. The `v >= 1_000_000` check in `level` correctly distinguishes these from 6-digit ZZ-level codes, since the maximum ZZ-level value (`110206`) is well below 1,000,000. The scheme is sound.

### 2. MEDIUM — Dead resolver `_resolve_building` is still present

**File:** `backend/app/utils/data_entry_emission_type_map.py:291-310`

The old `_resolve_building()` function (lines 291-310) is no longer referenced in `_RUNTIME_RESOLVERS` — it was replaced by `_resolve_building_rooms()`. It should be removed to avoid confusion.

### 3. MEDIUM — `_ROOM_TYPE_SUFFIX` is an identity map

**File:** `backend/app/utils/data_entry_emission_type_map.py:198-205`

```python
_ROOM_TYPE_SUFFIX: dict[str, str] = {
    "office": "office",
    "laboratories": "laboratories",
    ...
}
```

Every key equals its value. This could be simplified to a `set` (or `frozenset`) for validation, and just use `room_type` directly as the suffix. A set makes the intent clearer: "these are the valid room types."

### 4. MEDIUM — Duplicate color assignments in subcategory schemes

**File:** `frontend/src/constant/charts.ts`

In `buildings_energy_combustion`, both `combustion` and `natural_gas` map to `colors.value.apricot.darker`, and both `heating_thermal` and `heating_oil` map to `colors.value.apricot.dark`. If both the parent key and a child key appear simultaneously in a chart, they'll be indistinguishable. Verify whether the chart can show both levels at once; if so, the child should use a distinct shade.

### 5. LOW — `buildings_room` subcategory colors mix energy types and room types

**File:** `frontend/src/constant/charts.ts:330-340`

The `buildings_room` subcategory scheme contains both energy-type keys (`lighting`, `cooling`, etc.) and room-type keys (`office`, `laboratories`, etc.). When the chart drills down to WW-level, the subcategory key is the last segment (e.g., `office`). These are conceptually different dimensions — make sure the chart never shows both energy-type and room-type keys in the same series, or the legend will be confusing.

### 6. LOW — `hasattr(emission_type, "parent")` check is always true

**File:** `backend/app/modules/buildings/schemas.py:209`

```python
if not kwh_field and hasattr(emission_type, "parent"):
```

`parent` is a `@property` on the `EmissionType` enum — it always exists on every member. The check should be `if not kwh_field and emission_type.parent is not None:` to actually test whether a parent exists.

### 8. INFO — Chart key refactoring (display strings → snake_case)

The refactoring from display strings like `'Buildings energy consumption'` to `'buildings_energy_combustion'` across `CHART_CATEGORY_COLOR_SCHEMES`, `CHART_CATEGORY_COLOR_SCALES`, `CHART_SUBCATEGORY_COLOR_SCHEMES`, and `MODULE_TO_CATEGORIES` is clean and aligns frontend keys with backend `EmissionCategory` enum names. This is a good change.

### 9. INFO — `HeatingEnergyType` still defined in emission type map

**File:** `backend/app/utils/data_entry_emission_type_map.py:40-42`

`HeatingEnergyType` is still defined and used by the dead `_resolve_building()` function. Both can be removed together.

---

## Verdict

The feature logic is sound — the hierarchical emission type scheme extends cleanly to a 4th level. The main concerns are:

1. **Remove dead code** (`_resolve_building`, `HeatingEnergyType`) — easy cleanup
2. **Fix `hasattr` check** → `emission_type.parent is not None` — actual bug
3. **Verify chart color conflicts** at parent/child overlap — visual correctness

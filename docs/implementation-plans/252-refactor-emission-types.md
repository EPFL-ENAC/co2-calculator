# Emission Type Migration — Implementation Plan

# Spec-Driven Development

---

## Context

We are replacing the old `EmissionTypeEnum` (int-based, flat) with a new
`EmissionType` (6-digit positional int, hierarchical, with path/scope/level).

The main consumer is `DataEntryEmissionService.prepare_create()`, which today
contains a large `if/elif` block to map `DataEntryTypeEnum` → `EmissionType`,
and a separate ad-hoc `subcategory` string derivation.

Goal: make `prepare_create` fully generic — zero `if/elif` for emission type
resolution or subcategory derivation.

---

## Phase 1 — New enum + mapping (no DB change)

### 1.1 Add `emission_types.py`

- [x] Define `EmissionType(int, Enum)` with 6-digit positional scheme
- [x] Define `Scope(int, Enum)` and `EMISSION_SCOPE` dict
- [x] Add `.level`, `.path`, `.parent`, `.children()` helpers

### 1.2 Add `emission_type_mapping.py`

- [x] Define `DATA_ENTRY_TO_EMISSION_TYPES: dict[DataEntryTypeEnum, list[EmissionType] | None]`
- [x] Define sub-kind resolver maps (`_CLOUD_SUBKIND_MAP`, `_PLANE_CABIN_MAP`, etc.)
- [x] Define `resolve_emission_types(data_entry_type, data) -> list[EmissionType] | None`
- [x] Document legacy string renames for ctrl-F / ctrl-R

### 1.3 Tests for mapping

- [ ] Unit test: every `DataEntryTypeEnum` value resolves to a non-None `EmissionType`
      (except intentionally dynamic ones with known fallbacks)
- [ ] Unit test: `resolve_emission_types` for each dynamic case
      (all cabin classes, train classes, gas types, cloud sub_kinds)
- [ ] Unit test: `.level`, `.parent`, `.children()` helpers
- [ ] Unit test: `EMISSION_SCOPE` covers all leaf `EmissionType` values

---

## Phase 2 — Refactor `DataEntryEmissionService`

### 2.0 Drop `subcategory` column, add `scope` column to DB

**Drop `subcategory`:** Since `EmissionType.path` is now the canonical identifier,
the `subcategory` column is redundant and can be removed.

**Add `scope`:** Add `scope` column (1, 2, or 3) to enable fast aggregations:

```sql
SELECT scope, SUM(kg_co2eq) FROM data_entry_emissions GROUP BY scope
```

### 2.1 Replace the if/elif block

Current:

```python
# TODO: Make generic for all types!!!
if data_entry.data_entry_type == DataEntryTypeEnum.external_clouds:
    emission_type = EmissionType[data_entry.data.get("sub_kind") or "calcul"]
elif data_entry.data_entry_type == DataEntryTypeEnum.external_ai:
    emission_type = EmissionType.ai_provider
elif ...:
    emission_type = EmissionType.purchase
...
# END OF TODO
```

Target:

```python
emission_types = resolve_emission_types(
    data_entry.data_entry_type,
    data_entry.data,
)
if emission_types is None:
    logger.warning(f"Unhandled emission type: {data_entry.data_entry_type}")
    return []
if not emission_types:
    return []  # e.g. energy_mix — intentionally no rows
```

### 2.2 Return list of emissions (one per emission_type)

```python
# One row per emission_type — subcategory removed, use path for aggregation
return [
    DataEntryEmission(
        data_entry_id=data_entry.id,
        emission_type_id=emission_type.value,
        primary_factor_id=primary_factor_id,
        scope=emission_type.scope,  # from EMISSION_SCOPE dict
        kg_co2eq=emissions_value.get("kg_co2eq"),
        meta={**emissions_value},
    )
    for emission_type in emission_types
]
```

For treemaps or category aggregations, derive from `emission_type.path` or
`emission_type.parent` instead of using the old `subcategory` field.

### 2.3 Final shape of `prepare_create` → now returns a list

```python
async def prepare_create(self, data_entry) -> list[DataEntryEmission]:
    if not data_entry or data_entry.data_entry_type is None:
        return []

    # Generic emission type resolution — no if/elif
    emission_types = resolve_emission_types(data_entry.data_entry_type, data_entry.data)
    if emission_types is None:
        logger.warning(f"Unhandled emission type: {data_entry.data_entry_type}")
        return []
    if not emission_types:
        return []  # e.g. energy_mix — intentionally no rows

    handler = BaseModuleHandler.get_by_type(DataEntryTypeEnum(data_entry.data_entry_type))
    primary_factor_id = data_entry.data.get("primary_factor_id")
    if not primary_factor_id and handler.require_factor_to_match:
        return []

    factors = []
    factor_service = FactorService(self.session)
    if primary_factor_id:
        primary_factor = await factor_service.get(primary_factor_id)
        if not primary_factor:
            return []
        factors = [primary_factor]

    if data_entry.data_entry_type in (
        DataEntryTypeEnum.scientific, DataEntryTypeEnum.it, DataEntryTypeEnum.other
    ):
        electricity_factor = await factor_service.get_electricity_factor()
        if electricity_factor:
            factors.append(electricity_factor)

    emissions_value = await self._calculate_emissions(data_entry, factors=factors)

    if data_entry.id is None or emissions_value.get("kg_co2eq") is None:
        logger.error(f"No emissions calculated for DataEntry ID {data_entry.id}.")
        return []

    # One row per emission_type — scope derived from EMISSION_SCOPE
    return [
        DataEntryEmission(
            data_entry_id=data_entry.id,
            emission_type_id=emission_type.value,
            primary_factor_id=primary_factor_id,
            scope=get_scope(emission_type),
            kg_co2eq=emissions_value.get("kg_co2eq"),
            meta={**emissions_value},
        )
        for emission_type in emission_types
    ]
```

> **Note on multi-row kg_co2eq:** for member/building, each row currently gets
> the same total `kg_co2eq`. You'll likely want to split the value per
> emission_type using per-factor weights — that's a separate concern and can
> be addressed in the calculation logic, not here.

### 2.4 Update `emission_breakdown.py` to use parent/path

Replace subcategory-based grouping with path-based:

```python
def get_category_from_emission_type(emission_type: EmissionType) -> str:
    # e.g., "professional_travel__planes__eco" → "Professional Travel"
    return emission_type.parent.name.replace("_", " ").title() if emission_type.parent else "Uncategorized"

def get_chart_key_from_emission_type(emission_type: EmissionType) -> str:
    # e.g., "professional_travel__planes__eco" → "eco"
    return emission_type.name.split("__")[-1]
```

### 2.5 Tests for refactored service

- [ ] For each `DataEntryTypeEnum`, assert `emission_type_id` matches expected int value
- [ ] For dynamic types, assert correct leaf is resolved per `data` payload
- [ ] Assert `scope` matches expected scope (1, 2, or 3)
- [ ] Assert old `subcategory` values are no longer used; derive categories from `path` or `parent`

---

## Phase 3 — DB migration (optional, non-breaking)

The new `EmissionType` int values are **different** from the old ones.
Old DB rows still have old `emission_type_id` values (1, 2, 7, 1000, etc.).

Two options:

### Option A — Keep old ints, add a mapping column (safest)

- Add column `emission_type_path: str` to `data_entry_emissions`
- Drop `subcategory` column
- Backfill using `LEGACY_MIGRATION` dict
- New rows written with both `emission_type_id` (new int) and `emission_type_path`
- Old rows queried via `emission_type_path` after backfill

### Option B — Migrate emission_type_id in place

- Write a migration script using `LEGACY_MIGRATION` dict
- UPDATE `data_entry_emissions SET emission_type_id = <new> WHERE emission_type_id = <old>`
- Requires careful transaction + rollback plan
- Once done, old ints are gone — cleaner long term

**Recommendation:** Option B if you control all consumers of `emission_type_id`.
Option A if external systems (exports, dashboards) hardcode old int values.

### Phase 3 checklist

- [ ] Audit all consumers of `emission_type_id` (queries, exports, frontend filters)
- [ ] Drop `subcategory` column from `data_entry_emissions` table
- [ ] Add `scope` column to `data_entry_emissions` table
- [ ] Choose Option A or B
- [ ] Write + review migration script
- [ ] Run on staging, verify row counts per old/new value
- [ ] Deploy behind feature flag, run on prod

---

## Open questions (mark as resolved before closing)

- [x] `buildings__rooms__heating_thermal` — scope 1 ✓
- [x] `purchases__additional` — scope 1 ✓
- [x] Cabin class key for planes → `cabin_class` ✓
- [x] Cabin class key for trains → also `cabin_class` (values: `class_1` / `class_2`) ✓
- [x] Frontend/reports hardcode old subcategory strings → NO ✓
- [x] `energy` (old id=1) → kept as `EmissionType.energy = 1`, conversion factor only, never emits rows ✓
- [x] **Multi-row kg_co2eq split**: each row gets its own value from its own factor formula — no splitting needed. The calculation layer handles this naturally per-factor. ✓
- [x] Drop `subcategory` column — use `EmissionType.path` instead ✓
- [x] Add `scope` column — fast aggregations ✓
- [x] Update `emission_breakdown.py` to use `parent`/`path` instead of `subcategory` ✓

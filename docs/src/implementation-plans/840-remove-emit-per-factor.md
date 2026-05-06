---
status: delivered
issue: 840
last_updated: 2026-05-06
title: "Remove emit_per_factor — always emit one emission per factor"
summary: "Eliminate the emit_per_factor branch in prepare_create(); always emit one DataEntryEmission per factor."
---

# Plan: Remove `emit_per_factor` — Always Emit One Emission per Factor

## Context

The `prepare_create()` method in `data_entry_emission_service.py` has two code paths:

- **`emit_per_factor=True`** (lines 154-198): creates one `DataEntryEmission` per factor, using `factor.emission_type_id`
- **`emit_per_factor=False`** (lines 200-255): aggregates multiple factors into one `DataEntryEmission` row, summing `kg_co2eq` values

Only headcount (member/student) uses `emit_per_factor=True`. All other handlers use the default `False` and always resolve exactly **1 factor** per computation — so the aggregation loop effectively produces 1 row anyway.

**Goal:** Remove the branching. Always create one `DataEntryEmission` per factor. No intermediate aggregation in Python.

## Impact Analysis

| Handler                                                   | Current factors per comp                | Behavior change                                                                                                            |
| --------------------------------------------------------- | --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Headcount (member/student)                                | Many (food, waste, commuting sub-types) | None — already `emit_per_factor=True`                                                                                      |
| All others (travel, purchase, equipment, buildings, etc.) | 1                                       | Minimal — `emission_type_id` sourced from `factor.emission_type_id` instead of `emission_type.value` (should be identical) |

## Changes

### 1. `backend/app/models/data_entry_emission.py`

- Remove `emit_per_factor` field from `EmissionComputation` (lines 332-335)

### 2. `backend/app/modules/headcount/schemas.py`

- Remove `emit_per_factor=True` from both `MemberHandler.resolve_computations()` (line 193) and `StudentHandler.resolve_computations()` (line 249)

### 3. `backend/app/services/data_entry_emission_service.py` — `prepare_create()`

Replace the `if comp.emit_per_factor: ... else: ...` block (lines 154-255) with a single unified loop:

```python
for factor in factors:
    per_factor_kg = self._apply_formula(ctx, factor.values or {}, comp)
    if per_factor_kg is None:
        # log warning (keep existing missing-key diagnostics)
        continue

    # Compute quantity for meta (used by chart breakdown)
    quantity: float | None = None
    if comp.quantity_key and ctx.get(comp.quantity_key) is not None:
        base_qty = float(ctx[comp.quantity_key])
        multiplier = float(
            (factor.values or {}).get(comp.multiplier_key, comp.multiplier_default)
            if comp.multiplier_key
            else comp.multiplier_default
        )
        quantity = base_qty * multiplier
    quantity_unit: str | None = (factor.values or {}).get("unit")

    results.append(
        DataEntryEmission(
            data_entry_id=data_entry.id,
            emission_type_id=factor.emission_type_id,
            primary_factor_id=factor.id,
            kg_co2eq=per_factor_kg,
            meta={
                "factors_used": [{"id": factor.id, "values": factor.values}],
                "quantity": quantity,
                "quantity_unit": quantity_unit,
                **ctx,
            },
        )
    )
```

The CSV `kg_co2eq` override (lines 143-152) stays but applies per-factor instead of once.

### 4. `backend/app/utils/emission_category.py`

- Remove the comment referencing "pre-emit_per_factor" (line 731). The `HEADCOUNT_PER_FTE_KG` fallback itself can stay — it only triggers when no real emission rows exist, which handles truly legacy data.

## Files touched

1. `backend/app/models/data_entry_emission.py` — remove field
2. `backend/app/modules/headcount/schemas.py` — remove kwarg
3. `backend/app/services/data_entry_emission_service.py` — simplify `prepare_create()`
4. `backend/app/utils/emission_category.py` — update comment

## Verification

1. `pytest backend/` — run full backend test suite
2. Specifically check headcount emission tests produce the same per-sub-type rows
3. Check that non-headcount handlers still produce correct single-factor emissions
4. Verify chart breakdown endpoint returns correct values (emission_category tests)

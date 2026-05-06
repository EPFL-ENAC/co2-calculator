---
status: delivered
issue: 840
last_updated: 2026-05-06
title: "Replace distance_km / weight_kg with polymorphic additional_value on data_entry_emission"
summary: "Replace the two typed columns with a polymorphic additional_value field on data_entry_emission."
---

# Plan: Replace `distance_km` / `weight_kg` with a polymorphic `additional_value` on `data_entry_emission`

## Context

Branch `feat/840-store-and-aggregate-distance-and-weight` currently adds two
typed columns to `data_entry_emissions`: `distance_km FLOAT NULL` and
`weight_kg FLOAT NULL`. Commuting emissions populate `distance_km`; food/waste
emissions populate `weight_kg`. Travel is intentionally out of scope for
the first cut even though it would round out `total_distance_km`.

**Problem:** Two columns don't scale. The next physical metric (kwh for
electricity, chf for purchases, hours for facility usage…) would mean another
column and another aggregation tuple element. The unit is fully derivable from
`emission_type_id`, so encoding it in the column name is redundant.

**Goal:**

1. Replace the two columns with a single polymorphic `additional_value FLOAT NULL`.
   Unit is inferred from `EmissionType` in code.
2. Propagate the aggregated additional value through
   `carbon_report_modules.stats` and `carbon_reports.stats` so the reporting
   overview reads it from cached stats instead of re-aggregating from raw
   `DataEntryEmission` rows (the END GOAL the user called out).
3. Add the same plumbing for `professional_travel` (plane + train) so
   `total_distance_km` is complete on day one.

The branch hasn't been merged; the existing alembic revision is rewritten in
place rather than added as a fix-up.

---

## Approach

### 1 — Schema (alembic + model)

**Rewrite migration** `backend/alembic/versions/2026_04_24_1328-0bf6b8778dd9_add_distance_km_and_weight_kg_to_data_.py`
in place. Rename the file slug too (keep the same revision id `0bf6b8778dd9`):

```python
def upgrade() -> None:
    op.add_column(
        "data_entry_emissions",
        sa.Column(
            "additional_value",
            sa.Float(),
            nullable=True,
            comment=(
                "Polymorphic physical quantity tied to this emission row. "
                "Unit is inferred from emission_type_id "
                "(e.g. km for commuting and travel, kg for food and waste)."
            ),
        ),
    )

def downgrade() -> None:
    op.drop_column("data_entry_emissions", "additional_value")
```

**Model change** in `backend/app/models/data_entry_emission.py` (the field
block at lines ~360–368): drop `distance_km` and `weight_kg`, add
`additional_value: float | None = Field(default=None, ...)` with the same
description as the migration comment.

### 2 — Unit-resolution helper

Add to `backend/app/utils/emission_category.py` (near the existing
`EmissionCategory` block, ~lines 31-47):

```python
def additional_value_unit(et: EmissionType) -> str | None:
    """Unit of the additional_value column for a given EmissionType."""
    name = et.name
    if name.startswith("commuting") or name.startswith("professional_travel"):
        return "km"
    if name.startswith(("food", "waste")):
        return "kg"
    return None
```

This replaces the inline dispatch currently at emission_category.py:689-694
and also covers `professional_travel__plane*` / `professional_travel__train*`.

### 3 — Write path (service)

`backend/app/services/data_entry_emission_service.py:236-266` currently:

- Computes `distance_km` / `weight_kg` separately
- Stuffs them into `meta_extras` AND passes them as columns

Replace lines 236-256 with:

```python
additional_value: float | None = quantity if (
    quantity is not None
    and additional_value_unit(comp.emission_type) is not None
) else None
```

And remove the `distance_km=`, `weight_kg=`, `meta_extras` arguments from the
`DataEntryEmission(...)` constructor call. The duplication into `meta` goes
away — `meta` keeps `factors_used`, `quantity`, `quantity_unit`, and `**ctx`,
which is enough traceability. The column is the source of truth.

**New behavior** for travel: `professional_travel__plane*` and
`professional_travel__train*` will now populate `additional_value` because
their `quantity_key` is already `"distance_km"` (see
professional_travel/schemas.py:282, 342).

### 4 — Aggregation (repository)

`backend/app/repositories/data_entry_emission_repo.py:246-307`,
`get_emission_breakdown_with_quantity`. Change the SELECT from two sums to
one and the return shape from a 5-tuple to a 4-tuple:

```python
async def get_emission_breakdown_with_quantity(
    self, carbon_report_id: int,
) -> list[tuple[int, int, float, float | None]]:
    """Returns [(module_type_id, emission_type_id, sum_kg_co2eq,
    sum_additional_value), ...]"""
    query: Select[Any] = (
        select(
            col(CarbonReportModule.module_type_id),
            col(DataEntryEmission.emission_type_id),
            func.sum(col(DataEntryEmission.kg_co2eq)).label("total"),
            func.sum(col(DataEntryEmission.additional_value)).label(
                "sum_additional_value"
            ),
        )
        # ...joins / where unchanged...
        .group_by(
            col(CarbonReportModule.module_type_id),
            col(DataEntryEmission.emission_type_id),
        )
    )
```

### 5 — Chart builder (emission_category.py)

`build_chart_breakdown` at emission_category.py:617-761. Update the row
signature and the inline dispatch (lines 676, 689-697):

```python
for row in rows:
    module_type_id, emission_type_id, kg_co2eq, sum_additional_value = row
    # ...
    if category in ADDITIONAL_BREAKDOWN_ORDER:
        sub = additional_data.setdefault(category, {})
        sub[emission_type] = kg_co2eq
        unit = additional_value_unit(emission_type)
        if sum_additional_value is not None and unit is not None:
            qty_map = additional_quantities.setdefault(category, {})
            qty_map[emission_type] = (sum_additional_value, unit)
        additional_kg += kg_co2eq
```

The `_build_emission_value` / `_build_category_row` helpers and the rest of
the function keep their current behavior. `professional_travel` doesn't go
through `ADDITIONAL_BREAKDOWN_ORDER`, so its additional_value flows into
`module_breakdown` instead — extend `_build_category_row` to also receive
quantities (currently it only does so for additional rows) so plane/train
distances surface in the chart payload.

### 6 — Stats propagation (the END GOAL)

This is the new piece beyond the existing branch.

**`backend/app/repositories/data_entry_emission_repo.py:get_stats`** —
extend to optionally aggregate a second field. Cleanest path is a sibling
method `get_stats_pair` returning `(by_kg: dict[str,float],
by_additional: dict[str,float|None])` from one query, so we don't query
twice. Both group by the same key.

**`backend/app/services/carbon_report_module_service.py:compute_module_stats`** (lines 34-85):
add a new positional arg `additional_values: dict[str, float | None]` and
include `"by_additional_value": {...}` in the returned dict (only keys with
non-null/non-zero values, mirroring the existing `by_et` filter at line 61).

**`recompute_stats`** (carbon_report_module_service.py:220-273): change the
emission_repo call to fetch both maps in one go and pass the additional map
to `compute_module_stats`.

**`backend/app/services/carbon_report_service.py:recompute_report_stats`** (lines 99-196):
mirror the `by_emission_type` merge for `by_additional_value` — sum across
modules, keep null when no module contributed. Add the merged dict to the
final `stats = {...}` payload at line 168.

**`backend/app/models/carbon_report.py`** — extend the docstrings on
`CarbonReport.stats` and `CarbonReportModule.stats` to mention
`by_additional_value`.

### 7 — Consumer of cached stats (no aggregation needed)

`backend/app/repositories/carbon_report_module_repo.py:566-590`
(`get_reporting_overview`) currently builds chart rows from cached
`stats.by_emission_type` and pads with `None, None` for the distance/weight
slots. After the refactor, it pulls `stats.by_additional_value` and emits
4-tuples — no extra DB round-trip, which is exactly the user's stated goal.

### 8 — `data_entry_repo.py` cleanup

The diff at `app/repositories/data_entry_repo.py` had branching logic that
read `data_entry.data.get("distance_km")` then fell back to
`_emission.meta.get("distance_km")`. With `additional_value` as the source of
truth, replace both fallbacks with `_emission.additional_value` (and apply
the unit from `emission_type` if needed for downstream display).

### 9 — Tests

Update / rewrite the three modified test files:

- `tests/unit/repositories/test_data_entry_emission_repo.py` — replace the
  two `test_emission_breakdown_with_quantity_*` tests with versions that use
  `additional_value=` field and assert a single `sum_additional_value` per
  group. Add a case asserting that food + commuting in the same module yield
  separate per-`emission_type_id` entries.
- `tests/unit/services/test_data_entry_emission_service.py` — collapse the
  `TestMetaExtras` class: one test per category (commuting, food, waste,
  plane, train) asserting `additional_value` is set and `meta` is NOT
  duplicating it.
- `tests/unit/utils/test_emission_category.py` — update `_row()` helper to
  build 4-tuples; add coverage for `additional_value_unit()` and for the
  travel dispatch path.

Add a new test under `tests/unit/services/` for
`compute_module_stats` covering the new `by_additional_value` key, and a
test for `recompute_report_stats` confirming the merge.

### 10 — `app/api/v1/carbon_report_module_stats.py`

The diff added a `_dist, _wt` unpack. Reduce to a single `_add` (or simply
use named tuple access) to match the new 4-element shape from the repo.

---

## Critical Files

| File                                              | Change                                                                                   |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `alembic/versions/2026_04_24_1328-...py`          | Rewrite to add `additional_value`                                                        |
| `app/models/data_entry_emission.py`               | Replace 2 cols with `additional_value`                                                   |
| `app/utils/emission_category.py`                  | New `additional_value_unit()`; update `build_chart_breakdown` row shape and dispatch     |
| `app/services/data_entry_emission_service.py`     | Single assignment, drop meta duplication                                                 |
| `app/repositories/data_entry_emission_repo.py`    | Update `get_emission_breakdown_with_quantity`; new pair-aggregation for stats            |
| `app/services/carbon_report_module_service.py`    | Extend `compute_module_stats` with `by_additional_value`                                 |
| `app/services/carbon_report_service.py`           | Merge `by_additional_value` in report stats                                              |
| `app/repositories/carbon_report_module_repo.py`   | `get_reporting_overview` reads from cached `by_additional_value` instead of `None, None` |
| `app/repositories/data_entry_repo.py`             | Read `_emission.additional_value` instead of meta fallback                               |
| `app/api/v1/carbon_report_module_stats.py`        | Update tuple unpack                                                                      |
| `app/models/carbon_report.py`                     | Update stats docstrings                                                                  |
| 3 test files modified by the branch + 2 new tests | See §9                                                                                   |

---

## Verification

1. **Migration round-trips:**
   `cd backend && rtk alembic upgrade head && rtk alembic downgrade -1 && rtk alembic upgrade head`
2. **Unit + repo tests:**
   `cd backend && rtk uv run pytest tests/unit -k "emission or stats or carbon_report" -v`
3. **End-to-end stats refresh:**
   - Pick a fixture report with headcount + travel + food data
   - Trigger `recompute_stats` for one module via the existing endpoint
   - Inspect `carbon_report_modules.stats` JSON: confirm `by_additional_value`
     contains keys for commuting / food / waste / plane / train and
     `by_emission_type` is unchanged in shape
   - Inspect `carbon_reports.stats`: confirm merged `by_additional_value`
4. **Chart payload parity:**
   `rtk uv run pytest tests/integration -k "chart" -v` — assert the chart
   builder still emits the same `quantity` and `quantity_unit` per emission row.
5. **No double-write to meta:**
   `rg "meta_extras" backend/app` returns nothing.
6. **ERD doc** at `docs/src/database/erd.md` (already touched in the branch
   diff) — re-export with the new column.

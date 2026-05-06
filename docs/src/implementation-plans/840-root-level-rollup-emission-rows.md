---
status: delivered
issue: 840
last_updated: 2026-05-06
title: "Root-Level Rollup DataEntryEmission Rows"
summary: "Add root-level rollup rows on DataEntryEmission to support aggregate views."
---

# Plan: Root-Level Rollup `DataEntryEmission` Rows

PR: [#648](https://github.com/.../pull/648) — related issue: #841
Depends on: #840 (`emit_per_factor` removal — already landed on `feat/840-remove-emit-per-factor`)

## Context

Today, one `DataEntry` can produce multiple `DataEntryEmission` leaf rows (headcount sub-types, building room/energy combinations, travel cabin classes, etc.). As a result, sorting/querying by `kg_co2eq` per data entry requires a `GROUP BY + SUM` subquery — see `get_submodule_data()` in `backend/app/repositories/data_entry_repo.py:354-363`:

```python
emission_agg = (
    select(
        DataEntryEmission.data_entry_id,
        func.sum(DataEntryEmission.kg_co2eq).label("total_kg_co2eq"),
        func.min(DataEntryEmission.primary_factor_id).label("primary_factor_id"),
    )
    .group_by(col(DataEntryEmission.data_entry_id))
    .subquery()
)
```

This pattern:

- requires a subquery + group_by every time we want a total per entry
- makes `ORDER BY kg_co2eq` pay the full aggregation cost (table-scan of emissions) per request
- was identified as the blocker to enabling the `kg_co2eq` column sort in sprint 6

**Goal:** store a single **rollup** `DataEntryEmission` row per multi-leaf data entry containing the per-entry total. Identify it by `scope = None`. Queries that want the per-entry total JOIN directly on the rollup row (`AND scope IS NULL`) instead of aggregating.

## Design Principles

1. **One rollup row per data entry** — only for data entry types that actually produce multiple leaves (buildings rooms, potentially others). Single-leaf types don't need it: the leaf row already holds the total.
2. **`scope = None` as the marker** — no schema migration. `Scope` is already nullable in practice because `EMISSION_SCOPE` only registers leaves; rollup rows use parent emission types which are intentionally absent from `EMISSION_SCOPE`.
3. **Rollup rows are never counted in aggregations** — every SQL `SUM(kg_co2eq)` over emissions must gain a `scope IS NOT NULL` filter, otherwise we double-count (leaf + rollup).
4. **No new table / no schema migration** — rollups live in `data_entry_emission` alongside leaves.
5. **Headcount is out of scope** — the headcount submodule table does not display `kg_co2eq`, so rollups add cost with no benefit. Leaves remain the only rows.

## Impact Analysis

| Data entry type                                                                                   | # leaves today                 | Needs rollup? | Reason                                                                    |
| ------------------------------------------------------------------------------------------------- | ------------------------------ | ------------- | ------------------------------------------------------------------------- |
| `building`                                                                                        | up to 5 (energies × room_type) | **Yes**       | Sortable in submodule table; breakdown chart reads both leaves and totals |
| `member` / `student` (headcount)                                                                  | 3 (food/waste/commuting)       | No            | Not shown as `kg_co2eq` in UI table                                       |
| `plane` / `train` / `energy_combustion` / `process_emissions` / `external_clouds` / `external_ai` | 1                              | No            | Leaf is already the total                                                 |
| All other single-leaf types                                                                       | 1                              | No            | Leaf is already the total                                                 |

## Changes

### 1. `backend/app/utils/data_entry_emission_type_map.py`

Add a new mapping identifying the rollup parent emission type per data entry type, and the set of leaf emission types it aggregates:

```python
DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION: dict[DataEntryTypeEnum, EmissionType] = {
    DataEntryTypeEnum.building: EmissionType.buildings__rooms,
    # add here when a new type gains multi-leaf behavior
}
```

Only types in this mapping receive a rollup row. No entry = no rollup (single-leaf types).

### 2. `backend/app/services/data_entry_emission_service.py` — `prepare_create()`

After the per-factor loop has produced the list of leaf `DataEntryEmission` rows, append the rollup row if the type is registered:

```python
rollup_type = DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION.get(data_entry.data_entry_type)
if rollup_type is not None and results:
    total = sum(r.kg_co2eq or 0.0 for r in results)
    results.append(
        DataEntryEmission(
            data_entry_id=data_entry.id,
            emission_type_id=rollup_type.value,
            primary_factor_id=None,           # no single factor drives a rollup
            kg_co2eq=total,
            meta={"is_rollup": True},
        )
    )
```

Notes:

- The rollup's `emission_type_id` points at the parent type (`buildings__rooms = 60100`), which is **not** in `EMISSION_SCOPE` → `build_chart_breakdown()` already skips it (no double-counting in charts).
- `primary_factor_id=None` avoids implying any one factor is authoritative.
- `is_rollup: True` in `meta` is diagnostic only; the authoritative marker is the absence of scope on the emission type.

### 3. `backend/app/repositories/data_entry_repo.py` — `get_submodule_data()`

Replace the subquery-based aggregation with a direct `aliased` JOIN on the rollup emission. For data entries that can have a rollup, the rollup row **is** the total; for single-leaf types, the one leaf is the total.

```python
from sqlalchemy.orm import aliased

rollup = aliased(DataEntryEmission)

statement = (
    sa_select(DataEntry, rollup.kg_co2eq.label("total_kg_co2eq"), Factor, ...)
    .join(
        rollup,
        (col(rollup.data_entry_id) == col(DataEntry.id))
        & (rollup.scope.is_(None)),           # rollup row OR single-leaf row
        isouter=True,
    )
    ...
)

sort_map["kg_co2eq"] = rollup.kg_co2eq
```

Caveat: for single-leaf types the leaf has `scope` **set** (it's a registered leaf), not NULL. We have two options:

- **Option A (preferred)**: always create a rollup row, even for single-leaf types. Trivial cost (1 extra row), uniform query. `DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION` becomes the mapping _every_ data entry type → its parent.
- **Option B**: in the JOIN, `scope IS NULL OR (single-leaf entry)`. Adds branching.

Pick Option A for consistency. Update §1 accordingly: every `DataEntryTypeEnum` maps to a rollup parent (single-leaf types can reuse the leaf's parent, or the leaf itself if no parent exists — but with `is_rollup=True` meta and a zero-sum guard to avoid inserting an obvious duplicate, we just set `kg_co2eq = leaf_kg_co2eq`).

### 4. `backend/app/repositories/data_entry_emission_repo.py`

Add `DataEntryEmission.scope.is_not(None)` (or equivalently `EmissionType.scope` join filter) to every aggregation that sums over `kg_co2eq`. The callsites to audit (from the PR description):

1. `get_breakdown_by_emission_type()` (emission breakdown endpoint)
2. `get_totals_per_category()` (module totals)
3. `get_top_class_breakdown()` (top-class chart)
4. `get_per_person_totals()` (per-person chart)

Each needs:

```python
.where(DataEntryEmission.scope.is_not(None))
```

Note: `scope` is not a column on `DataEntryEmission` — it's derived via `EMISSION_SCOPE.get(emission_type)`. The actual filter is `DataEntryEmission.emission_type_id.in_(LEAF_EMISSION_TYPE_IDS)` or equivalently "the emission type appears in `EMISSION_SCOPE`". Implement as:

```python
LEAF_EMISSION_TYPE_IDS = {et.value for et in EMISSION_SCOPE.keys()}
...
.where(col(DataEntryEmission.emission_type_id).in_(LEAF_EMISSION_TYPE_IDS))
```

Compute `LEAF_EMISSION_TYPE_IDS` once at module load.

### 5. `backend/app/utils/emission_category.py` — `build_chart_breakdown()`

No change required: it already iterates `MODULE_BREAKDOWN_ORDER` (leaves only) and skips anything not in `EMISSION_SCOPE`. Rollup rows will be skipped for free.

Add a one-line comment documenting this invariant so the next person doesn't remove it:

```python
# NOTE: rollup rows (scope=None) are silently skipped because their
# emission type is not registered in EMISSION_SCOPE. Do not widen this.
```

### 6. Tests

- **`test_data_entry_emission_service.py`** — assert that creating a building data entry produces N leaf rows **and** 1 rollup row (`emission_type_id == buildings__rooms`, `primary_factor_id is None`, `kg_co2eq == sum(leaves)`).
- **`test_data_entry_repo.py`** — assert that sorting the buildings submodule by `kg_co2eq` returns rows in descending order, using the rollup row (no subquery).
- **Emission repo tests** — assert that aggregation endpoints (breakdown, totals, top-class, per-person) exclude rollup rows (i.e., results match pre-rollup baseline).
- **Integration test** — create buildings + plane + headcount, validate the submodule table `kg_co2eq` column matches `sum(leaves)` per row for all three.

## Files touched

1. `backend/app/utils/data_entry_emission_type_map.py` — new `DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION` mapping
2. `backend/app/services/data_entry_emission_service.py` — append rollup row in `prepare_create()`
3. `backend/app/repositories/data_entry_repo.py` — swap subquery for aliased JOIN in `get_submodule_data()`; `sort_map["kg_co2eq"]` points at the rollup
4. `backend/app/repositories/data_entry_emission_repo.py` — add leaf-only filter to 4 aggregation queries
5. `backend/app/utils/emission_category.py` — doc comment
6. `backend/tests/` — fixtures + new assertions

## Data migration (TODO from PR #648)

Existing production `DataEntry` rows will not have rollup emissions. Ship a one-off script (`scripts/backfill_rollup_emissions.py`):

```python
# Pseudocode
for dt in DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION:
    for de in session.exec(select(DataEntry).where(data_entry_type_id == dt)):
        leaves = session.exec(
            select(DataEntryEmission)
            .where(data_entry_id == de.id, scope.is_not(None))
        ).all()
        if not leaves:
            continue
        session.add(DataEntryEmission(
            data_entry_id=de.id,
            emission_type_id=DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION[dt].value,
            kg_co2eq=sum(l.kg_co2eq for l in leaves),
            meta={"is_rollup": True, "backfilled": True},
        ))
session.commit()
```

Idempotent: before insert, check there isn't already a rollup row for that data entry.

## Verification

1. `pytest backend/` — full suite green
2. Buildings submodule table: sort by `kg_co2eq` ascending and descending — order matches manual computation
3. Emission breakdown chart / per-person chart / top-class chart — values unchanged vs. `dev` (rollups excluded correctly)
4. Query plan inspection: `EXPLAIN ANALYZE` on `get_submodule_data` shows no subquery, a single hash/nested-loop JOIN on the rollup
5. Backfill script on a staging DB — compare chart totals pre/post backfill, expect no change

## Relation to #841

#841 proposes making `EmissionType` the single source of truth (explicit `parent`, explicit `scope`, no integer parsing). That refactor would:

- replace `DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION` with `emission_type.parent` traversal
- replace `LEAF_EMISSION_TYPE_IDS = {EMISSION_SCOPE...}` with `emission_type.is_leaf` / `emission_type.scope is not None`

We can ship this plan first (rollup rows live, `scope=None` contract established), then #841 later refactors the mapping plumbing without changing the storage contract. Alternatively we do #841 first, which halves the diff here (no `LEAF_EMISSION_TYPE_IDS` set — just `emission_type.scope IS NOT NULL` via a JOIN). **Recommendation**: if #841 is realistically doable in the current sprint, do it first; otherwise ship this plan now and treat #841 as a follow-up refactor.

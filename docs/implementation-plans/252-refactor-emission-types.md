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

-- DESISION RECORD --

## Design Recommendation: **Don't aggregate into the tree — keep leaves only**

Storing intermediate nodes is a classic premature optimization that creates more problems than it solves.

### Problems with storing intermediate nodes

**Data integrity nightmare.** Every time you update/delete a leaf emission, you need to cascade-update all ancestor nodes. With concurrent writes, you'll get race conditions and stale aggregates. This is essentially a cache invalidation problem in your DB.

**Double-counting risk.** Any query that doesn't carefully filter out non-leaf nodes will silently overcount. This will bite you (or a future dev) eventually.

**Write amplification.** One leaf insert = N writes (leaf + subcategory + category + root). For your headcount case that already produces 4 rows, you'd be writing ~12 rows.

**Schema confusion.** `DataEntryEmission` linked to `data_entry_id` makes sense for a leaf. What does it mean for a `buildings` aggregate row? Which `data_entry_id` does it belong to? What `primary_factor_id`?

---

### The right approach: **Compute aggregates at query time**

Your `EmissionType` enum already has everything you need — `parent`, `level`, `children()`. Use that structure in your queries/services.

```python
def get_subtree_values(root: EmissionType) -> list[int]:
    """Get all leaf emission_type_ids under a given node."""
    if not root.children():
        return [root.value]
    result = []
    for child in root.children():
        result.extend(get_subtree_values(child))
    return result

# Then in your query layer:
def sum_kg_co2eq_for_node(session, node: EmissionType, filters=...) -> float:
    leaf_ids = get_subtree_values(node)
    return session.exec(
        select(func.sum(DataEntryEmission.kg_co2eq))
        .where(DataEntryEmission.emission_type_id.in_(leaf_ids))
        .where(...)  # date range, org, etc.
    ).one()
```

For treemaps, you'd do one query per top-level category, or a single query grouped by `emission_type_id` and then roll up in Python using your enum hierarchy — which is fast since it's just dict operations.

---

### If performance becomes a real concern later

Add a **materialized view** or a **separate `emission_aggregates` table** that's explicitly a cache, clearly decoupled from `data_entry_emissions`. Rebuild it async on a schedule or after bulk imports. But don't do this now — you almost certainly won't need it.

---

**TL;DR:** Leaves only. Aggregate in the service/query layer using your `EmissionType` tree. Your enum already made the right design decision — trust it.

--

# For carbon_report_modules

## Recommended `stats` shape

```python
{
  # --- Totals by scope ---
  "scope1": 1234.5,
  "scope2": 5678.9,
  "scope3": 9012.3,
  "total": 15925.7,

  # --- By emission type (leaves only, sparse — omit zeros) ---
  "by_emission_type": {
    "60101": 123.4,   # buildings__rooms__lighting
    "60102": 456.7,   # buildings__rooms__cooling
    "60104": 789.0,   # buildings__rooms__heating_elec
    "60105": 100.0,   # buildings__rooms__heating_thermal
    "60200": 50.0,    # buildings__combustion
  },

  # --- Meta ---
  "computed_at": "2025-03-01T12:00:00Z",
  "formula_version": "abc123",
  "entry_count": 342,     # how many data_entries were included
  "missing_factors": 3,   # data quality signal
}
```

**Store leaves only** in `by_emission_type`. Any subtree rollup (e.g. `buildings__rooms`) is derived at read-time using your `EmissionType` enum — same pattern as before, just over a dict instead of 8M DB rows.

```python
def rollup(stats: dict, node: EmissionType) -> float:
    leaf_ids = get_subtree_values(node)  # your existing helper
    by_et = stats.get("by_emission_type", {})
    return sum(by_et.get(str(lid), 0.0) for lid in leaf_ids)

# e.g.
rollup(stats, EmissionType.buildings__rooms)  # → sum of 60101+60102+60103+60104+60105
rollup(stats, EmissionType.buildings)         # → all buildings leaves
```

---

## When to recompute

Invalidate and recompute the module stats when:

- Any `data_entry` under that module is created/updated/deleted
- Any `data_entry_emission` is recomputed (factor change, formula version bump)
- On-demand via an admin action

Set `status` to a `stale` value during invalidation so the API can signal to the frontend that stats are being recalculated — your `status` field on `carbon_report_modules` is perfect for this.

---

## What this gives you

| Need                    | How                                                             |
| ----------------------- | --------------------------------------------------------------- |
| Treemap for a report    | iterate `carbon_report_modules`, rollup each node from `stats`  |
| Scope breakdown         | direct from `stats.scope1/2/3`                                  |
| Cross-report comparison | query `carbon_report_modules` by `module_type_id`, read `stats` |
| Drill-down to entries   | still go to `data_entry_emissions` — now rare/intentional       |
| Data freshness signal   | `stats.computed_at` + module `status`                           |

The 8M-row scan becomes a `SELECT stats FROM carbon_report_modules WHERE carbon_report_id = ?` — effectively free.

Got it. Here's my read of the cleanest architecture given everything:

**Core insight:** There are exactly two retrieval strategies, and one computation pattern:

```
Strategy A — primary_factor_id:  factor = get(id)           → 1 factor → 1 row
Strategy B — classification:     factors = get_by(kind, subkind, **ctx) → N factors → N rows
```

The handler per `DataEntryType` declares:

1. Which strategy to use per `EmissionType`
2. What context to extract from `data_entry.data` for the query
3. Which formula key to apply (`kg_co2eq_per_fte`, `kg_co2eq_per_kwh`, etc.)

---

## Implementation Plan

### Layer 1 — Data structures (pure, no DB)

```python
@dataclass
class FactorQuery:
    """Descriptor returned by a handler telling FactorService what to fetch."""
    data_entry_type: DataEntryTypeEnum
    kind: str | None = None        # e.g. "food", "heating", "plane"
    subkind: str | None = None     # e.g. "vegetarian", "elec", "business"
    # Extra runtime context passed as filters to FactorService
    # e.g. {"building_name": "BC", "distance_km": 1200}
    context: dict[str, Any] = field(default_factory=dict)

@dataclass
class EmissionComputation:
    """One unit of work: factor query + formula key + emission type."""
    emission_type: EmissionType
    # Either factor_id (Strategy A) or a query descriptor (Strategy B)
    factor_id: int | None = None
    factor_query: FactorQuery | None = None
    # Key in factor.values used by the formula
    formula_key: str = "kg_co2eq_per_kwh"
    # Key in data_entry.data used by the formula
    quantity_key: str = "quantity"
```

### Layer 2 — Handler contract

Each handler implements **one method** per `EmissionType` it owns, registered via a decorator:

```python
class BaseModuleHandler:
    _registry: dict[EmissionType, Callable] = {}

    @classmethod
    def register(cls, *emission_types: EmissionType):
        """Decorator: maps EmissionType(s) → resolver method."""
        def decorator(fn):
            for et in emission_types:
                cls._registry[et] = fn
            return fn
        return decorator

    def resolve_computations(
        self,
        data_entry: DataEntry | DataEntryResponse,
        emission_types: list[EmissionType],
    ) -> list[EmissionComputation]:
        """Dispatch each emission_type to its registered resolver."""
        results = []
        for et in emission_types:
            resolver = self._registry.get(et)
            if resolver is None:
                logger.warning(f"No resolver for {et.name!r}")
                continue
            computations = resolver(self, data_entry, et)
            results.extend(computations)  # always a list
        return results
```

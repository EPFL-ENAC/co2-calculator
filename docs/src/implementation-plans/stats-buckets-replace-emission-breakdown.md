# Stats buckets: replace emission-breakdown with persisted report stats

**Status:** delivered (2026-07-07)
**Branch:** `refactor/reduce-data-entry-emission-type-reach`

Deviations from the original spec, as shipped:

- Bucket keys reuse the old `EmissionCategory` values
  (`buildings_energy_combustion`, `buildings_room`, …) so i18n keys and
  chart colors survive unchanged.
- `total` (kg) stays all-inclusive (additional buckets included), matching
  the historical headline and the backoffice `stats["total"]` SQL ordering;
  the per-bucket `additional` flag carries the split.
- Report stats keep flat `scope1/2/3`, `by_emission_type`,
  `by_additional_value` alongside `buckets` for existing consumers
  (backoffice CSV export, research-facility computed providers).
- `DataEntryEmission.scope` persists on, derived from bucket membership
  (`emission_type_scope` in the registry). LN2 `purchases__additional` rows
  move from scope 1 to scope 3, matching what the chart always displayed.
- New read endpoints: `GET /modules-stats/{id}/report-stats` (stats +
  validated headline, the store's post-mutation refresh path) and
  `GET /modules-stats/{id}/validated-totals` (was referenced by the
  frontend but never existed).
- The frontend keeps its chart row shapes via
  `src/utils/emissionStatsAdapter.ts`; `exclude_modules` became a
  client-side display filter. Emission-type id → name mapping is generated
  into `src/types/emission-taxonomy.gen.ts` by `make gen-emission-taxonomy`.
- The IT section carries `percentage_of_source_modules`, `cloud_ai_detail`
  and `validated_sources` so the IT page needs no client-side math.

## Problem

The results charts are fed by `build_chart_breakdown`
(`app/utils/emission_category.py`), which re-aggregates raw
`data_entry_emissions` rows at read time into a bespoke payload
(`module_breakdown` / `additional_breakdown` / `per_person_breakdown` /
`it_summary` / …). This duplicates what `recompute_stats` already persists in
`carbon_report_module.stats`, and it rests on two artificial concepts:

- `EmissionCategory` — a 12-value enum that is `ModuleTypeEnum` in disguise,
  except buildings is split in two and headcount/embodied ride in an
  "additional" list.
- `Scope` on every `EmissionType` node — only consumed as a rollup filter;
  the chart's scope bands are hardcoded frontend-side (`CATEGORY_SCOPE` in
  `ModuleCarbonFootprintChart.vue`).

There is also a naming collision: `app/models/taxonomy.py` (a Pydantic
response schema) vs `app/modules/emissions/taxonomy.py` (the domain enum).

## Design

### StatBucket — modules declare their display semantics

Each module's `emissions.py` declares its stat buckets; the emissions
registry aggregates them in display order:

```python
@dataclass(frozen=True)
class StatBucket:
    key: str                      # stable snake_case payload key
    scope: int                    # 1 | 2 | 3 — chart band
    roots: tuple[EmissionType, ...]
    exclude: tuple[EmissionType, ...] = ()
    additional: bool = False      # additional breakdown, not in org total
```

- Most modules: one bucket (key = module name, whole subtree).
- Buildings: `buildings_combustion` (scope 1: `buildings__combustion` +
  `buildings__rooms__heating_thermal`), `buildings_rooms` (scope 2: rooms
  minus heating_thermal), `embodied_energy` (scope 3, additional).
- Headcount: `commuting`, `food`, `waste` (scope 3, all additional).

`Scope`, `EmissionCategory`, `EmissionMeta`, `_SCOPE_CATEGORY_ROOTS` and the
scope/category properties are deleted from `taxonomy.py`; it keeps only the
`EmissionType` enum, parent/children derivation, and tree helpers.

### Persisted shapes

`carbon_report_module.stats` (written by `recompute_stats`):

```jsonc
{
  "buckets": {
    "<bucket_key>": {
      "scope": 1,
      "additional": false,
      "total_kg": 0.0,
      "by_emission_type": { "<et_id>": 0.0 }, // leaves + rollups
      "by_additional_value": { "<et_id>": 0.0 },
    },
  },
  "total_kg": 0.0, // non-additional buckets only
  "entry_count": 0,
  "computed_at": "iso",
}
```

The buildings embodied bucket additionally carries `by_building` and
`by_category` (building-name detail is not derivable from emission types, so
it is queried once at recompute time instead of at read time).

`carbon_report.stats` (written by `recompute_report_stats_many`, pure merge
of child module stats + statuses — no DB aggregation):

```jsonc
{
  "buckets": {/* merged, ordered by registry bucket order */},
  "per_fte": { "<bucket_key>": 0.0 }, // tonnes per FTE
  "validated_buckets": ["<bucket_key>"],
  "total_tonnes": 0.0,
  "validated_total_tonnes": 0.0,
  "total_fte": 0.0,
  "it": {
    "total_tonnes": 0.0,
    "percentage_of_total": 0.0,
    "per_fte": 0.0,
    "categories": {
      "it_equipment": 0.0,
      "it_purchases": 0.0,
      "cloud_ai": 0.0,
      "research": 0.0,
    },
  },
  "computed_at": "iso",
}
```

### Read path

- `GET emission-breakdown` and the repo path feeding it die; the frontend
  reads `carbon_report.stats` / `carbon_report_module.stats` directly.
- `results-summary` stays an endpoint but becomes a thin read of the current
  and previous-year report stats + the car-km factor (previous-year data can
  change after this report is computed, so it cannot be persisted here).
- `it-breakdown` merges into the report stats `it` section (incl. purchase
  `top_class_detail` persisted at recompute).

### Frontend

- Chart components group bars by the `scope` field on each bucket;
  the hardcoded `CATEGORY_SCOPE` map is deleted.
- `stores/modules.ts`, results/print composables and OpenAPI types move to
  the stats shapes. Backend stays the source of all numbers (per-FTE, IT
  share, validated totals are read, never recomputed client-side).

### Naming

- `app/models/taxonomy.py` → `app/schemas/taxonomy.py` (`TaxonomyNode` is a
  response schema, not a model). `app/modules/emissions/taxonomy.py` keeps
  its name and becomes a pure taxonomy file.

## Delivery tiers

1. **Backend buckets:** `StatBucket` + per-module declarations + registry
   order; `compute_module_stats` and `_build_report_stats` emit the new
   shapes; embodied by_building/by_category persisted at recompute.
2. **Backend read path:** delete `build_chart_breakdown` /
   `emission_category.py` / `EmissionCategory` / `Scope`; endpoints serve
   stats; `results-summary` thin read; schema move for `TaxonomyNode`.
3. **Frontend:** stats-shaped consumption, delete `CATEGORY_SCOPE`,
   regenerate OpenAPI types.

Tests ship with each tier (bucket math, report merge, endpoint contracts).

# Chart Data Endpoints — TDD Implementation Plan

## Context

The results page charts (`ModuleCarbonFootprintChart` and `CarbonFootPrintPerPersonChart`) currently use **hardcoded mock data**. We need a backend endpoint that returns real aggregated emission data so both charts can display actual values. Headcount-derived categories (food, waste, commuting, grey_energy) don't have real data yet — use arbitrary per-FTE placeholders.

The existing pro travel implementation (`get_travel_stats_by_class`) serves as a pattern — it returns **chart-ready data** (treemap format matching `TreeMapModuleChart.vue`). We follow the same principle: backend returns data in the exact shape the frontend charts expect. Key principle: **tests first**, extract calculations into pure functions.

---

## Approach

### Endpoint: `GET /{carbon_report_id}/emission-breakdown`

Single endpoint serving both results page charts. Returns **chart-ready data** with keys matching the existing frontend ECharts dataset dimensions exactly (e.g., `unitGas`, `cooling`, `scientific`, `plane`). No frontend transformation needed.

The per-module treemap endpoint (`GET /{unit_id}/{year}/{module_id}/emission-breakdown`) is deferred to a follow-up.

---

## Step 1: Pure Calculation Functions + Tests (TDD)

**Create** `backend/app/utils/emission_breakdown.py` — pure functions, no DB:

```python
# ── Mapping constants ──────────────────────────────────────────────

# Maps (module_type_id, subcategory) → frontend chart key
# Used by ModuleCarbonFootprintChart for subcategory-level stacked bars
SUBCATEGORY_TO_CHART_KEY: dict[tuple[int, str], str] = {
    # Equipment (module_type_id=4)
    (4, "Scientific"): "scientific",
    (4, "It"): "it",
    (4, "Other"): "other",
    # Professional Travel (module_type_id=2)
    (2, "plane"): "plane",
    (2, "train"): "train",
    # Infrastructure (module_type_id=3)
    (3, "cooling"): "cooling",
    (3, "ventilation"): "ventilation",
    (3, "lighting"): "lighting",
    # Purchase (module_type_id=5)
    (5, "bioChemicals"): "bioChemicals",
    (5, "consumables"): "consumables",
    (5, "equipment"): "equipment",
    (5, "services"): "services",
    # External Cloud & AI (module_type_id=7)
    (7, "scitas"): "scitas",
    (7, "rcp"): "rcp",
    # Internal Services (module_type_id=6) — single subcategory
    (6, None): "itInfrastructure",
    # Global Energy (module_type_id=99) — two separate categories
    (99, "unit_gas"): "unitGas",
    (99, "infrastructure_gas"): "infrastructureGas",
}

# Maps emission_type_id → headcount chart key (additional data toggle)
EMISSION_TYPE_TO_HEADCOUNT_KEY: dict[int, str] = {
    3: "food",        # EmissionTypeEnum.food
    4: "waste",       # EmissionTypeEnum.waste
    5: "commuting",   # EmissionTypeEnum.commuting
    6: "greyEnergy",  # EmissionTypeEnum.grey_energy
}

# Maps module_type_id → per-person chart key
# Used by CarbonFootPrintPerPersonChart for module-level aggregation
MODULE_TYPE_TO_PER_PERSON_KEY: dict[int, str] = {
    99: None,  # global_energy splits into unitGas + infrastructureGas (special case)
    3: "infrastructure",
    4: "equipment",
    6: "itInfrastructure",
    2: "professionalTravel",
    5: "purchases",
    7: "researchCoreFacilities",
}

# Headcount placeholder per-FTE values (kg CO2eq per FTE per year)
# Used when headcount module is validated but real emission data isn't available
HEADCOUNT_PER_FTE_KG: dict[str, float] = {
    "food": 420.0,       # ~420 kg CO2eq/FTE/year
    "waste": 125.0,      # ~125 kg CO2eq/FTE/year
    "commuting": 1375.0, # ~1375 kg CO2eq/FTE/year
    "greyEnergy": 500.0, # ~500 kg CO2eq/FTE/year
}

# Category ordering — must match scope 1/2/3 grouping in the chart
# Scope 1: Unit Gas (0), Infrastructure Gas (1)
# Scope 2: Infrastructure (2), Equipment (3), IT Infrastructure (4)
# Scope 3: Professional Travel (5), Purchases (6), Research Core Facilities (7)
MODULE_BREAKDOWN_ORDER = [
    "Unit Gas", "Infrastructure Gas", "Infrastructure", "Equipment",
    "IT Infrastructure", "Professional Travel", "Purchases",
    "Research Core Facilities",
]

# ── Pure functions ─────────────────────────────────────────────────

def build_chart_breakdown(
    rows: list[tuple[int, int, str | None, float]],
    # Each row: (module_type_id, emission_type_id, subcategory, kg_co2eq)
    total_fte: float = 0.0,
    headcount_validated: bool = False,
) -> dict:
    """
    Transforms raw DB emission rows into chart-ready format for both
    ModuleCarbonFootprintChart and CarbonFootPrintPerPersonChart.

    Returns:
    {
        "module_breakdown": [
            # One dict per category bar, ordered by MODULE_BREAKDOWN_ORDER
            # Each dict has: category (str) + subcategory chart keys (float)
            # + corresponding StdDev keys (float, 0.0 placeholder for now)
            {"category": "Equipment", "scientific": 10.0, "scientificStdDev": 0.0,
             "it": 3.0, "itStdDev": 0.0, "other": 0.2, "otherStdDev": 0.0},
            ...
        ],
        "additional_breakdown": [
            # Headcount-derived categories (shown when toggle is on)
            {"category": "Commuting", "commuting": 11.0, "commutingStdDev": 0.0},
            {"category": "Food", "food": 2.1, "foodStdDev": 0.0},
            {"category": "Waste", "waste": 0.6, "wasteStdDev": 0.0},
            {"category": "Grey Energy", "greyEnergy": 2.5, "greyEnergyStdDev": 0.0},
        ],
        "per_person_breakdown": {
            # Module-level aggregation for CarbonFootPrintPerPersonChart
            # Values = module total tonnes / FTE
            "unitGas": 2.5, "infrastructureGas": 2.0, "infrastructure": 8.3,
            "equipment": 5.5, "itInfrastructure": 5.0, "professionalTravel": 18.4,
            "purchases": 39.1, "researchCoreFacilities": 3.0,
            "commuting": 11.0, "food": 2.1, "waste": 0.6, "greyEnergy": 2.5,
            "stdDev": 0
        },
        "total_tonnes_co2eq": float,
        "total_fte": float
    }
    """

def build_treemap(
    rows: list[tuple[str, float]],
    # Each row: (subcategory_name, kg_co2eq)
) -> list[dict]:
    """
    Returns: [{"name": str, "value": float, "percentage": float}]
    For travel modules (with cabin_class detail), parent caller provides
    pre-grouped data and this just computes percentages.
    """
```

**Create** `backend/tests/unit/utils/test_emission_breakdown.py` — write FIRST:

| Test                                              | What it verifies                                                                  |
| ------------------------------------------------- | --------------------------------------------------------------------------------- |
| `test_build_chart_breakdown_basic`                | Multiple modules map to correct chart keys with correct values in tonnes          |
| `test_build_chart_breakdown_empty_input`          | Returns `{module_breakdown: [], additional_breakdown: [], total: 0}`              |
| `test_build_chart_breakdown_category_ordering`    | Categories appear in MODULE_BREAKDOWN_ORDER (scope 1/2/3 grouping preserved)      |
| `test_build_chart_breakdown_headcount_additional` | Headcount placeholder data lands in `additional_breakdown` not `module_breakdown` |
| `test_build_chart_breakdown_headcount_per_fte`    | Placeholder values scale with FTE: `HEADCOUNT_PER_FTE_KG[key] * total_fte / 1000` |
| `test_build_chart_breakdown_no_headcount`         | When `headcount_validated=False`, `additional_breakdown` is empty                 |
| `test_build_chart_breakdown_per_person`           | Per-person values = module total kg / FTE / 1000                                  |
| `test_build_chart_breakdown_per_person_zero_fte`  | When FTE=0, per-person values are all 0 (no division by zero)                     |
| `test_build_chart_breakdown_stddev_keys`          | Each subcategory key has a corresponding `*StdDev` key (0.0 placeholder)          |
| `test_build_chart_breakdown_null_filtered`        | None/null kg_co2eq values excluded from aggregation                               |
| `test_build_treemap_basic`                        | Correct treemap nesting with percentages                                          |
| `test_build_treemap_zero_total`                   | Returns empty list                                                                |

---

## Step 2: Repository Methods + Tests

**Modify** `backend/app/repositories/data_entry_emission_repo.py`:

Add `get_emission_breakdown(carbon_report_id)`:

- Same join pattern as `get_stats_by_carbon_report_id` (line 158)
- Add `emission_type_id` and `subcategory` to SELECT and GROUP BY
- Returns raw tuples: `[(module_type_id, emission_type_id, subcategory, sum_kg_co2eq), ...]`

**Extend** `backend/tests/unit/repositories/test_data_entry_emission_repo.py`:

| Test                                                  | What it verifies                                     |
| ----------------------------------------------------- | ---------------------------------------------------- |
| `test_get_emission_breakdown_basic`                   | Multi-module aggregation with emission_type grouping |
| `test_get_emission_breakdown_validated_only`          | Non-validated modules excluded                       |
| `test_get_emission_breakdown_null_emissions_filtered` | NULL kg_co2eq rows excluded                          |
| `test_get_emission_breakdown_empty`                   | No data returns empty list                           |

---

## Step 3: Service Layer

**Modify** `backend/app/services/data_entry_emission_service.py`:

Add thin wrapper (following existing pattern at line 184):

- `get_emission_breakdown(carbon_report_id)` → calls repo `get_emission_breakdown()`

No service-level tests needed — the service is a one-line delegation. Logic is tested in pure function tests (Step 1) and repo tests (Step 2).

---

## Step 4: API Endpoint

**Modify** `backend/app/api/v1/carbon_report_module_stats.py`:

### `GET /{carbon_report_id}/emission-breakdown`

```python
@router.get("/{carbon_report_id}/emission-breakdown")
async def get_emission_breakdown(
    carbon_report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    # 1. Get raw emission rows (repo)
    emission_rows = await DataEntryEmissionService(db).get_emission_breakdown(
        carbon_report_id=carbon_report_id
    )
    # 2. Get FTE (reuse existing pattern from validated-totals endpoint)
    fte_stats = await DataEntryService(db).get_stats_by_carbon_report_id(
        carbon_report_id=carbon_report_id,
    )
    total_fte = sum(fte_stats.values())

    # 3. Check if headcount module is validated
    headcount_validated = await _is_module_validated(
        db, carbon_report_id, ModuleTypeEnum.headcount
    )

    # 4. Transform to chart-ready format (pure function)
    return build_chart_breakdown(
        rows=emission_rows,
        total_fte=total_fte,
        headcount_validated=headcount_validated,
    )
```

Response example:

```json
{
  "module_breakdown": [
    { "category": "Unit Gas", "unitGas": 2.5, "unitGasStdDev": 0.0 },
    {
      "category": "Infrastructure Gas",
      "infrastructureGas": 2.0,
      "infrastructureGasStdDev": 0.0
    },
    {
      "category": "Infrastructure",
      "cooling": 9.0,
      "coolingStdDev": 0.0,
      "ventilation": 3.0,
      "ventilationStdDev": 0.0,
      "lighting": 9.0,
      "lightingStdDev": 0.0
    },
    {
      "category": "Equipment",
      "scientific": 10.0,
      "scientificStdDev": 0.0,
      "it": 3.0,
      "itStdDev": 0.0,
      "other": 0.2,
      "otherStdDev": 0.0
    },
    {
      "category": "IT Infrastructure",
      "itInfrastructure": 25.0,
      "itInfrastructureStdDev": 0.0
    },
    {
      "category": "Professional Travel",
      "train": 1.5,
      "trainStdDev": 0.0,
      "plane": 3.0,
      "planeStdDev": 0.0
    },
    {
      "category": "Purchases",
      "bioChemicals": 2.0,
      "bioChemicalsStdDev": 0.0,
      "consumables": 3.0,
      "consumablesStdDev": 0.0,
      "equipment": 1.0,
      "equipmentStdDev": 0.0,
      "services": 2.0,
      "servicesStdDev": 0.0
    },
    {
      "category": "Research Core Facilities",
      "scitas": 1.0,
      "scitasStdDev": 0.0,
      "rcp": 1.5,
      "rcpStdDev": 0.0
    }
  ],
  "additional_breakdown": [
    { "category": "Commuting", "commuting": 8.0, "commutingStdDev": 0.0 },
    { "category": "Food", "food": 2.5, "foodStdDev": 0.0 },
    { "category": "Waste", "waste": 10.0, "wasteStdDev": 0.0 },
    { "category": "Grey Energy", "greyEnergy": 4.0, "greyEnergyStdDev": 0.0 }
  ],
  "per_person_breakdown": {
    "unitGas": 2.5,
    "infrastructureGas": 2.0,
    "infrastructure": 8.3,
    "equipment": 5.5,
    "itInfrastructure": 5.0,
    "professionalTravel": 18.4,
    "purchases": 39.1,
    "researchCoreFacilities": 3.0,
    "commuting": 11.0,
    "food": 13.0,
    "waste": 0.0,
    "greyEnergy": 0.0,
    "stdDev": 0
  },
  "total_tonnes_co2eq": 61.7,
  "total_fte": 25.5
}
```

All values are in **tonnes CO2eq** (kg / 1000). Keys match the existing frontend ECharts dataset dimensions exactly.

**Frontend usage:**

- `ModuleCarbonFootprintChart`: `module_breakdown` is the base `datasetSource`. When "additional data" toggle is on, append `additional_breakdown` items. No key mapping needed — keys match existing series `encode.y` values.
- `CarbonFootPrintPerPersonChart`: `per_person_breakdown` becomes the "My Unit" row. Keys match existing series `encode.y` values.
- Scope 1/2/3 overlays: `module_breakdown` ordering is fixed (matches `MODULE_BREAKDOWN_ORDER`), so the existing `graphic` rectangle positions remain correct.

---

## Step 5: Frontend Integration

**Modify** `frontend/src/stores/modules.ts` — add state + action (following existing `getTravelStatsByClass` pattern):

```typescript
// State
emissionBreakdown: null as EmissionBreakdownResponse | null,
loadingEmissionBreakdown: false,
errorEmissionBreakdown: null as string | null,

// Action
async function getEmissionBreakdown(carbonReportId: number) {
  loadingEmissionBreakdown = true;
  errorEmissionBreakdown = null;
  try {
    const data = await api
      .get(`modules-stats/${carbonReportId}/emission-breakdown`)
      .json<EmissionBreakdownResponse>();
    emissionBreakdown = data;
  } catch (err) { ... }
  finally { loadingEmissionBreakdown = false; }
}
```

**Modify** `frontend/src/pages/app/ResultsPage.vue`:

- Import module store
- Fetch emission breakdown when carbon report changes (need `carbon_report_id` — available from timeline store or derive from `unitId` + `year`)
- Pass breakdown data as props to both chart components:

```html
<ModuleCarbonFootprintChart
  :view-uncertainties="viewUncertainties"
  :breakdown-data="moduleStore.emissionBreakdown"
/>
<CarbonFootPrintPerPersonChart
  :view-uncertainties="viewUncertainties"
  :per-person-breakdown="moduleStore.emissionBreakdown?.per_person_breakdown"
/>
```

**Modify** `frontend/src/components/charts/results/ModuleCarbonFootprintChart.vue`:

- Add prop: `breakdownData?: { module_breakdown: Array<Record<string, unknown>>, additional_breakdown: Array<Record<string, unknown>> } | null`
- Replace hardcoded `datasetSource` computed:
  - When `breakdownData` is available: use `module_breakdown` as base, append `additional_breakdown` when toggle is on
  - When `breakdownData` is null: return empty array (show empty/loading state)
- **Keep all existing**: series definitions, colors, scope graphic overlays, tooltip formatter, download PNG/CSV, markLine uncertainty logic
- The series `encode.y` values (`unitGas`, `cooling`, `scientific`, etc.) already match the response keys — no changes needed to series config

**Modify** `frontend/src/components/charts/results/CarbonFootPrintPerPersonChart.vue`:

- Add prop: `perPersonBreakdown?: Record<string, number> | null`
- Replace hardcoded "My unit" row: use values from `perPersonBreakdown`
- Keep "EPF" and "Objective 2030" as hardcoded benchmark rows
- Show empty/loading state when prop is null

---

## Files Modified

| File                                                                       | Change                                                  |
| -------------------------------------------------------------------------- | ------------------------------------------------------- |
| `backend/app/utils/emission_breakdown.py`                                  | **NEW** — pure mapping functions + constants            |
| `backend/tests/unit/utils/test_emission_breakdown.py`                      | **NEW** — TDD tests for pure functions                  |
| `backend/app/repositories/data_entry_emission_repo.py`                     | Add `get_emission_breakdown` query method               |
| `backend/tests/unit/repositories/test_data_entry_emission_repo.py`         | Add repo tests                                          |
| `backend/app/services/data_entry_emission_service.py`                      | Add thin service wrapper                                |
| `backend/app/api/v1/carbon_report_module_stats.py`                         | Add endpoint                                            |
| `frontend/src/stores/modules.ts`                                           | Add state + `getEmissionBreakdown` action               |
| `frontend/src/pages/app/ResultsPage.vue`                                   | Fetch breakdown data, pass as props                     |
| `frontend/src/components/charts/results/ModuleCarbonFootprintChart.vue`    | Accept `breakdownData` prop, remove hardcoded mock      |
| `frontend/src/components/charts/results/CarbonFootPrintPerPersonChart.vue` | Accept `perPersonBreakdown` prop, remove hardcoded mock |

---

## Verification

1. Run `pytest backend/tests/unit/utils/test_emission_breakdown.py` — all pure function tests pass
2. Run `pytest backend/tests/unit/repositories/test_data_entry_emission_repo.py` — all repo tests pass
3. `GET /api/v1/modules-stats/{id}/emission-breakdown` returns correct chart-ready structure
4. Only validated modules appear in results
5. Category ordering matches scope 1/2/3 grouping (Unit Gas, Infra Gas, Infra, Equipment, IT, Travel, Purchases, Research)
6. Empty report returns `{module_breakdown: [], additional_breakdown: [], total_tonnes_co2eq: 0}`
7. Frontend charts render with real data from API
8. "Additional data" toggle still works — shows/hides commuting, food, waste, grey energy bars
9. Empty/loading states display correctly when no data
10. `npm run lint && npm run type-check` — no errors

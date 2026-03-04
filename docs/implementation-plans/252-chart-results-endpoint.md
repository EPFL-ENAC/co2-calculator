# Chart Data Endpoints — Implementation Plan

## Context

The results page charts (`ModuleCarbonFootprintChart` and `CarbonFootPrintPerPersonChart`) previously used **hardcoded mock data**. A backend endpoint now returns real aggregated emission data so both charts display actual values. Headcount-derived categories (food, waste, commuting, grey energy) use arbitrary per-FTE placeholders when no real data exists.

Key design decisions made during implementation:

- **Automatic chart key derivation**: No hardcoded `(module_type_id, subcategory) → chart_key` mapping table. Instead, chart keys are derived automatically from the data — using the DB `subcategory` field for modules where it provides meaningful subdivisions (Equipment, Professional Travel), and `EmissionTypeEnum.name` for everything else.
- **Building split by emission type**: The Building module (module_type_id=3) is split into two separate x-axis bars — "Buildings energy consumption" (emission_type=energy) and "Buildings room" (emission_type=grey_energy) — via a `_MODULE_EMISSION_CATEGORY` override mapping.
- **Three-scope layout**: Scope 1 (Processes, Buildings energy consumption), Scope 2 (Buildings room, Equipment), Scope 3 (External cloud & AI, Purchases, Research facilities, Professional travel). Legacy categories (Unit Gas, Infrastructure Gas) were removed.
- **Validation-aware display**: Unvalidated module categories still appear in the chart with 0-height bars and greyed-out x-axis labels. The same applies to additional (headcount-derived) categories when headcount is not validated.
- **EPFL reference filtering**: The per-person chart only shows EPFL reference values for categories that are validated in the user's unit.
- **Processes placeholder**: A zero-filled "Processes" bar is always present (no module_type_id yet) for future Scope 1 process emissions.

---

## Approach

### Endpoint: `GET /{carbon_report_id}/emission-breakdown`

Single endpoint serving both results page charts. Returns **chart-ready data** with keys derived automatically from emission types and subcategories. Values are in **tonnes CO2eq** (kg / 1000).

---

## Step 1: Pure Calculation Functions + Tests (TDD)

**Created** `backend/app/utils/emission_breakdown.py` — pure functions, no DB:

### Constants

```python
from app.models.data_entry_emission import EmissionTypeEnum

# module_type_id → chart category (x-axis grouping)
# Building (module_type_id=3) is split by emission type; see _MODULE_EMISSION_CATEGORY
MODULE_TYPE_TO_CATEGORY: dict[int, str] = {
    4: "Equipment",
    6: "Research facilities",
    2: "Professional travel",
    5: "Purchases",
    7: "External cloud & AI",
}

# (module_type_id, emission_type_id) → category override
# Splits Building into two separate x-axis bars by emission type
_MODULE_EMISSION_CATEGORY: dict[tuple[int, int], str] = {
    (3, EmissionTypeEnum.energy): "Buildings energy consumption",
    (3, EmissionTypeEnum.grey_energy): "Buildings room",
}

_SUBCATEGORY_PREFERRED_MODULES: set[int] = {4, 2}  # Equipment, Professional Travel

HEADCOUNT_EMISSION_TYPES: set[int] = {
    EmissionTypeEnum.food, EmissionTypeEnum.waste,
    EmissionTypeEnum.commuting, EmissionTypeEnum.grey_energy,
}

MODULE_TYPE_TO_PER_PERSON_KEY: dict[int, str] = {
    3: "infrastructure", 4: "equipment", 6: "itInfrastructure",
    2: "professionalTravel", 5: "purchases", 7: "researchCoreFacilities",
}

CATEGORY_TO_MODULE_TYPE_IDS  # auto-derived from MODULE_TYPE_TO_CATEGORY + _MODULE_EMISSION_CATEGORY

HEADCOUNT_PER_FTE_KG: dict[str, float] = {
    "food": 420.0, "waste": 125.0, "commuting": 1375.0, "greyEnergy": 500.0,
}

# Scope 1 → Scope 2 → Scope 3 ordering
MODULE_BREAKDOWN_ORDER = [
    # Scope 1
    "Processes",
    "Buildings energy consumption",
    # Scope 2
    "Buildings room",
    "Equipment",
    # Scope 3
    "External cloud & AI",
    "Purchases",
    "Research facilities",
    "Professional travel",
]

CATEGORY_CHART_KEYS: dict[str, list[str]] = {
    "Processes": [],
    "Buildings energy consumption": ["energy"],
    "Buildings room": ["grey_energy"],
    "Equipment": ["scientific", "it", "other"],
    "External cloud & AI": ["stockage", "virtualisation", "calcul", "ai_provider"],
    "Purchases": [],
    "Research facilities": [],
    "Professional travel": ["plane", "train"],
}

ADDITIONAL_BREAKDOWN_ORDER = ["Commuting", "Food", "Waste", "Grey Energy"]
```

### Helper functions

```python
def _is_headcount_only(emission_type_id, module_type_id) -> bool:
    """Return True if this emission should be routed to additional_breakdown.

    Headcount emission types are normally headcount-derived.  However, if the
    (module, emission_type) pair has a specific category override in
    _MODULE_EMISSION_CATEGORY, it is real module data (e.g. grey_energy on
    Building → "Buildings room").
    """

def _get_category(module_type_id, emission_type_id) -> str | None:
    """Resolve the chart category for a (module, emission_type) pair.

    Checks _MODULE_EMISSION_CATEGORY overrides first (e.g. Building split),
    then falls back to MODULE_TYPE_TO_CATEGORY.
    """

def _to_chart_key(emission_type_id, subcategory, module_type_id) -> str | None:
    """Derive chart key automatically from the row data.

    For modules in _SUBCATEGORY_PREFERRED_MODULES (Equipment, Travel),
    uses the subcategory field (lowercased first char for camelCase).
    For everything else, uses EmissionTypeEnum.name.
    """
```

This means:

- **Equipment** (module_type_id=4): subcategories "Scientific"→`scientific`, "It"→`it`, "Other"→`other`
- **Professional Travel** (module_type_id=2): subcategories "plane"→`plane`, "train"→`train`
- **Building energy** (module_type_id=3, emission_type=1): emission type → `energy` → category "Buildings energy consumption"
- **Building room** (module_type_id=3, emission_type=6): emission type → `grey_energy` → category "Buildings room"
- **External cloud & AI** (module_type_id=7): emission types → `stockage`, `virtualisation`, `calcul`, `ai_provider`

### `build_chart_breakdown`

```python
def build_chart_breakdown(
    rows: list[tuple[int, int, str | None, float]],
    total_fte: float = 0.0,
    headcount_validated: bool = False,
    validated_module_type_ids: set[int] | None = None,
) -> dict:
```

**Returns:**

```json
{
  "module_breakdown": [
    { "category": "Processes" },
    {
      "category": "Buildings energy consumption",
      "energy": 9.0,
      "energyStdDev": 0.0
    },
    {
      "category": "Buildings room",
      "grey_energy": 0.0,
      "grey_energyStdDev": 0.0
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
      "category": "External cloud & AI",
      "stockage": 1.0,
      "stockageStdDev": 0.0,
      "virtualisation": 0.5,
      "virtualisationStdDev": 0.0,
      "calcul": 0.3,
      "calculStdDev": 0.0,
      "ai_provider": 0.0,
      "ai_providerStdDev": 0.0
    },
    { "category": "Purchases" },
    { "category": "Research facilities" },
    {
      "category": "Professional travel",
      "plane": 3.0,
      "planeStdDev": 0.0,
      "train": 1.5,
      "trainStdDev": 0.0
    }
  ],
  "additional_breakdown": [
    { "category": "Commuting", "commuting": 8.0, "commutingStdDev": 0.0 },
    { "category": "Food", "food": 2.5, "foodStdDev": 0.0 },
    { "category": "Waste", "waste": 0.6, "wasteStdDev": 0.0 },
    { "category": "Grey Energy", "greyEnergy": 2.5, "greyEnergyStdDev": 0.0 }
  ],
  "per_person_breakdown": {
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
  "validated_categories": [
    "Equipment",
    "Professional travel",
    "Commuting",
    "Food",
    "Waste",
    "Grey Energy"
  ],
  "total_tonnes_co2eq": 61.7,
  "total_fte": 25.5
}
```

**Key behaviors:**

- All categories in `MODULE_BREAKDOWN_ORDER` always appear (zero-filled when no data)
- "Processes" is a placeholder with no module_type_id; always zero-filled
- Both "Buildings energy consumption" and "Buildings room" are validated when module_type_id=3 is validated
- `grey_energy` from module_type_id=3 is NOT filtered as headcount — it maps to "Buildings room" via `_MODULE_EMISSION_CATEGORY`
- All 4 additional categories always appear (0 values when headcount not validated)
- `validated_categories` includes module categories whose `module_type_id`s are all validated, plus all 4 additional categories when `headcount_validated=True`
- Per-person breakdown aggregates at module level (not subcategory), divided by FTE

### `build_treemap`

```python
def build_treemap(rows: list[tuple[str, float]]) -> list[dict]:
    """Returns: [{"name": str, "value": float, "percentage": float}]"""
```

**Created** `backend/tests/unit/utils/test_emission_breakdown.py`:

| Test                                                                      | What it verifies                                                                  |
| ------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `test_build_chart_breakdown_basic`                                        | Equipment keeps scientific/it/other subdivisions; Travel keeps plane/train        |
| `test_build_chart_breakdown_emission_type_for_infra`                      | Building energy → "Buildings energy consumption" bar                              |
| `test_build_chart_breakdown_building_room`                                | Building grey_energy → "Buildings room" bar (not filtered as headcount)           |
| `test_build_chart_breakdown_emission_type_for_rcf`                        | External cloud & AI uses emission types stockage/virtualisation/calcul            |
| `test_build_chart_breakdown_empty_input`                                  | All categories present with zero values; additional categories present with zeros |
| `test_build_chart_breakdown_category_ordering`                            | Categories appear in MODULE_BREAKDOWN_ORDER                                       |
| `test_build_chart_breakdown_headcount_additional`                         | Headcount data in additional_breakdown, not module_breakdown                      |
| `test_build_chart_breakdown_headcount_per_fte`                            | Placeholder values scale with FTE                                                 |
| `test_build_chart_breakdown_no_headcount`                                 | When headcount not validated, additional categories still appear with 0 values    |
| `test_build_chart_breakdown_per_person`                                   | Per-person values = module total kg / FTE / 1000                                  |
| `test_build_chart_breakdown_per_person_zero_fte`                          | When FTE=0, per-person values are all 0 (no division by zero)                     |
| `test_build_chart_breakdown_stddev_keys`                                  | Each value key has a corresponding `*StdDev` key                                  |
| `test_build_chart_breakdown_null_filtered`                                | None/null kg_co2eq values excluded from aggregation                               |
| `test_build_chart_breakdown_subcategory_aggregation`                      | Multiple rows with same subcategory aggregate correctly                           |
| `test_build_chart_breakdown_validated_categories`                         | validated_categories reflects which modules are validated                         |
| `test_build_chart_breakdown_validated_includes_additional_when_headcount` | Additional categories validated when headcount is validated                       |
| `test_build_chart_breakdown_additional_not_validated_without_headcount`   | Additional categories NOT validated when headcount not validated                  |
| `test_build_treemap_basic`                                                | Correct treemap entries with percentages                                          |
| `test_build_treemap_zero_total`                                           | Returns empty list                                                                |

---

## Step 2: Repository Methods + Tests

**Modified** `backend/app/repositories/data_entry_emission_repo.py`:

Added `get_emission_breakdown(carbon_report_id)`:

- Joins `DataEntryEmission → DataEntry → CarbonReportModule`
- Filters: `carbon_report_id` match, `status == VALIDATED`, `kg_co2eq IS NOT NULL`
- Groups by `module_type_id`, `emission_type_id`, `subcategory`
- Returns raw tuples: `[(module_type_id, emission_type_id, subcategory, sum_kg_co2eq), ...]`

**Modified** `backend/app/repositories/data_entry_repo.py`:

- **Bugfix**: `float(total)` → `float(total) if total is not None else 0.0` to handle NULL SUM results

**Extended** `backend/tests/unit/repositories/test_data_entry_emission_repo.py`:

| Test                                                      | What it verifies                                     |
| --------------------------------------------------------- | ---------------------------------------------------- |
| `test_get_emission_breakdown_basic`                       | Multi-module aggregation with emission_type grouping |
| `test_get_emission_breakdown_aggregates_same_subcategory` | Multiple rows with same subcategory aggregate        |
| `test_get_emission_breakdown_validated_only`              | Non-validated modules excluded                       |
| `test_get_emission_breakdown_empty`                       | No data returns empty list                           |

---

## Step 3: Service Layer

**Modified** `backend/app/services/data_entry_emission_service.py`:

Added thin wrapper: `get_emission_breakdown(carbon_report_id)` → delegates to repo.

---

## Step 4: API Endpoint

**Modified** `backend/app/api/v1/carbon_report_module_stats.py`:

### `GET /{carbon_report_id}/emission-breakdown`

```python
@router.get("/{carbon_report_id}/emission-breakdown")
async def get_emission_breakdown(
    carbon_report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    # 1. Get raw emission rows (repo — only validated modules)
    emission_rows = await DataEntryEmissionService(db).get_emission_breakdown(
        carbon_report_id=carbon_report_id,
    )
    # 2. Get FTE totals
    fte_stats = await DataEntryService(db).get_stats_by_carbon_report_id(
        carbon_report_id=carbon_report_id, aggregate_by="module_type_id",
    )
    total_fte = sum(fte_stats.values())

    # 3. Query ALL module statuses for validation info
    module_statuses = {row[0]: row[1] for row in db.execute(
        select(CarbonReportModule.module_type_id, CarbonReportModule.status)
        .where(CarbonReportModule.carbon_report_id == carbon_report_id)
    ).all()}

    headcount_validated = (
        module_statuses.get(ModuleTypeEnum.headcount.value) == ModuleStatus.VALIDATED
    )
    validated_module_type_ids = {
        mid for mid, status in module_statuses.items()
        if status == ModuleStatus.VALIDATED
    }

    # 4. Transform to chart-ready format (pure function)
    return build_chart_breakdown(
        rows=emission_rows, total_fte=total_fte,
        headcount_validated=headcount_validated,
        validated_module_type_ids=validated_module_type_ids,
    )
```

---

## Step 5: Frontend Integration

### Store (`frontend/src/stores/modules.ts`)

- Added `EmissionBreakdownResponse` interface
- Added `emissionBreakdown` / `loadingEmissionBreakdown` / `errorEmissionBreakdown` state
- Added `getEmissionBreakdown(carbonReportId)` action

### ResultsPage (`frontend/src/pages/app/ResultsPage.vue`)

- Imports `useModuleStore`
- Calls `fetchEmissionBreakdown()` on mount and when carbon report changes
- Passes breakdown data as props to both chart components:

```html
<ModuleCarbonFootprintChart
  :view-uncertainties="viewUncertainties"
  :breakdown-data="moduleStore.state.emissionBreakdown"
/>
<CarbonFootPrintPerPersonChart
  :view-uncertainties="viewUncertainties"
  :per-person-breakdown="moduleStore.state.emissionBreakdown?.per_person_breakdown"
  :validated-categories="moduleStore.state.emissionBreakdown?.validated_categories"
  :headcount-validated="moduleStore.state.emissionBreakdown?.validated_categories?.includes('Commuting') ?? false"
/>
```

### ModuleCarbonFootprintChart (`frontend/src/components/charts/results/ModuleCarbonFootprintChart.vue`)

- Accepts `breakdownData` prop (type: `EmissionBreakdownResponse | null`)
- `datasetSource` uses `module_breakdown` as base; appends `additional_breakdown` when toggle is on
- **Category label mapping** via `CATEGORY_LABEL_MAP` translates backend category names to i18n keys for the x-axis
- **Series** (stacked bars) match chart keys from the backend:
  - Buildings energy consumption: `energy` (lilac.darker)
  - Buildings room: `grey_energy` (lilac.dark)
  - Equipment: `scientific`, `it`, `other` (mauve shades)
  - Professional travel: `plane`, `train` (babyBlue shades)
  - External cloud & AI: `stockage`, `virtualisation`, `calcul`, `ai_provider` (paleYellowGreen shades)
  - Additional: `commuting`, `food`, `waste`, `greyEnergy` (aqua/mint/periwinkle/skyBlue)
- **Validation-aware labels**: `xAxis.axisLabel.formatter` uses rich text — validated category names in black (10px), unvalidated in grey (10px)
- **Three-scope overlay** via `graphic` rectangles with graduated grey backgrounds:
  - Scope 1: lightest (`rgba(248,248,248)`) — Processes, Buildings energy consumption
  - Scope 2: light (`rgba(240,240,240)`) — Buildings room, Equipment
  - Scope 3: medium (`rgba(229,229,229)`) — External cloud & AI, Purchases, Research facilities, Professional travel
  - Additional categories: darker (`rgba(215,215,215)`) — shown only when toggle is on, with divider line
- **No y-axis cap**: `max` removed from yAxis config
- Removed all hardcoded mock data

### CarbonFootPrintPerPersonChart (`frontend/src/components/charts/results/CarbonFootPrintPerPersonChart.vue`)

- Accepts `perPersonBreakdown`, `validatedCategories`, and `headcountValidated` props
- **My Unit row**: directly uses `per_person_breakdown` values from the API
- **EPFL reference row**: hardcoded reference values, filtered to only show values for validated categories (via `CATEGORY_TO_PP_KEYS` mapping and `validatedPPKeys` computed)
- **Headcount validation placeholder**: when headcount is not validated, shows a validation prompt card instead of the chart
- `CATEGORY_TO_PP_KEYS` maps backend category names to per-person keys:
  - "Buildings energy consumption" / "Buildings room" → `['infrastructure']`
  - "Equipment" → `['equipment']`
  - "External cloud & AI" → `['researchCoreFacilities']`
  - "Research facilities" → `['itInfrastructure']`
  - "Professional travel" → `['professionalTravel']`
  - "Purchases" → `['purchases']`
  - "Processes" → `[]` (no per-person key yet)
- Removed legacy categories (Unit Gas, Infrastructure Gas) from series, dimensions, and data
- Removed hardcoded mock data for "My Unit" row

### i18n (`frontend/src/i18n/results.ts`)

Added translation keys:

| Key                                   | EN                           | FR                                   |
| ------------------------------------- | ---------------------------- | ------------------------------------ |
| `charts-processes-category`           | Processes                    | Processus                            |
| `charts-building-energy-subcategory`  | Buildings energy consumption | Consommation d'énergie des bâtiments |
| `charts-building-room-subcategory`    | Buildings room               | Locaux des bâtiments                 |
| `charts-research-facilities-category` | Research facilities          | Infrastructures de recherche         |

---

## Files Modified

| File                                                                       | Change                                                                                         |
| -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `backend/app/utils/emission_breakdown.py`                                  | **NEW** — pure functions + constants with automatic chart key derivation, building split logic |
| `backend/tests/unit/utils/test_emission_breakdown.py`                      | **NEW** — 19 TDD tests for pure functions                                                      |
| `backend/app/repositories/data_entry_emission_repo.py`                     | Add `get_emission_breakdown` query method                                                      |
| `backend/app/repositories/data_entry_repo.py`                              | Bugfix: handle NULL SUM results                                                                |
| `backend/tests/unit/repositories/test_data_entry_emission_repo.py`         | Add 4 repo tests                                                                               |
| `backend/app/services/data_entry_emission_service.py`                      | Add thin service wrapper                                                                       |
| `backend/app/api/v1/carbon_report_module_stats.py`                         | Add endpoint with validation status queries                                                    |
| `frontend/src/stores/modules.ts`                                           | Add state + `getEmissionBreakdown` action                                                      |
| `frontend/src/pages/app/ResultsPage.vue`                                   | Fetch breakdown data, pass as props                                                            |
| `frontend/src/components/charts/results/ModuleCarbonFootprintChart.vue`    | Building split series, 3-scope overlay, validation-aware labels, category renames              |
| `frontend/src/components/charts/results/CarbonFootPrintPerPersonChart.vue` | Updated category keys, headcount validation placeholder, EPFL filtering                        |
| `frontend/src/i18n/results.ts`                                             | Added Processes, building subcategory, and research facilities translation keys                |

---

## Verification

1. `pytest backend/tests/unit/utils/test_emission_breakdown.py` — all 19 pure function tests pass
2. `pytest backend/tests/unit/repositories/test_data_entry_emission_repo.py` — all repo tests pass
3. `GET /api/v1/modules-stats/{id}/emission-breakdown` returns correct chart-ready structure
4. Only validated modules contribute emission data
5. Category ordering follows scope grouping: Scope 1 (Processes, Buildings energy), Scope 2 (Buildings room, Equipment), Scope 3 (External cloud & AI, Purchases, Research facilities, Professional travel)
6. Building module split: energy → "Buildings energy consumption", grey_energy → "Buildings room" (not filtered as headcount)
7. All categories always present (zero-filled when no data or unvalidated), including "Processes" placeholder
8. Additional categories always present (0 values when headcount not validated, greyed-out labels)
9. Unvalidated category labels appear grey; validated labels appear black (10px font)
10. Three-scope overlay with graduated grey backgrounds (lightest → darkest) + darker additional category zone
11. Frontend charts render with real data from API
12. "Additional data" toggle shows/hides commuting, food, waste, grey energy bars
13. EPFL reference row in per-person chart only shows values for validated categories
14. Per-person chart shows validation prompt when headcount is not validated

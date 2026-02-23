# Test Plan: 252 Endpoints

## Problem

Business logic calculations are inline in the `get_results_summary` and `get_validated_totals` routes. They cannot be unit tested. They must first be extracted into pure functions.

---

## Step 1 — Extract calculations (prerequisite refactor)

### Create `backend/app/utils/report_computations.py`

Extract two pure functions (follows existing pattern: `utils/emission_breakdown.py`):

```python
def compute_validated_totals(
    emission_stats: dict[str, float],
    fte_stats: dict[str, float],
    headcount_type_id: str,
) -> dict:
    ...

def compute_results_summary(
    current_emissions: dict[str, float | None],
    current_fte: dict[str, float | None],
    prev_emissions: dict[str, float],
    co2_per_km_kg: float,
    headcount_key: str,
) -> dict:
    ...
```

### Update `carbon_report_module_stats.py`

Routes become simple dispatchers:

```python
from app.utils.report_computations import compute_validated_totals, compute_results_summary

# get_validated_totals route:
emission_stats = await DataEntryEmissionService(db).get_stats_by_carbon_report_id(...)
fte_stats = await DataEntryService(db).get_stats_by_carbon_report_id(...)
return compute_validated_totals(emission_stats, fte_stats, str(ModuleTypeEnum.headcount.value))

# get_results_summary route:
raw = await UnitTotalsService(db).get_results_summary(carbon_report_id)
return compute_results_summary(
    raw["current_emissions"],
    raw["current_fte"],
    raw["prev_emissions"],
    get_settings().CO2_PER_KM_KG,
    str(ModuleTypeEnum.headcount.value),
)
```

---

## Step 2 — Test inventory

### Testing approach

Tests use **realistic multi-module fixtures** that cover many edge cases in a single scenario, complemented by **targeted edge-case tests** for div/0 and None guards. This avoids trivial tests (e.g. "does dividing by 1000 work?") while giving strong coverage on the logic that actually breaks.

---

### 2a. `compute_validated_totals()` — pure, no DB

**File:** `backend/tests/unit/utils/test_compute_validated_totals.py`

#### Fixture: realistic multi-module scenario

```python
emission = {"1": 5000.0, "2": 25000.0, "4": 15000.0, "7": 3200.0}
fte = {"1": 120.0}
headcount_type_id = "1"
```

**Assertions on single call:**

| What                 | Expected                                |
| -------------------- | --------------------------------------- |
| `modules[1]`         | `120.0` (FTE wins for headcount module) |
| `modules[2]`         | `25.0` (25000 kg → 25.0 tonnes)         |
| `modules[4]`         | `15.0`                                  |
| `modules[7]`         | `3.2`                                   |
| module key order     | sorted by int: `[1, 2, 4, 7]`           |
| `total_tonnes_co2eq` | `48.2` (5000+25000+15000+3200)/1000     |
| `total_fte`          | `120.0`                                 |

#### Edge-case tests (parametrized)

| ID               | Input                                      | Expected                                              |
| ---------------- | ------------------------------------------ | ----------------------------------------------------- |
| both_empty       | `emission={}, fte={}`                      | `modules={}, total_tonnes=0.0, total_fte=0.0`         |
| zero_emission    | `emission={"4": 0.0, "2": 1000.0}, fte={}` | `modules={4:0.0, 2:1.0}, total_tonnes=1.0`            |
| zero_fte         | `emission={}, fte={"1": 0.0}`              | `modules={1: 0.0}, total_fte=0.0`                     |
| headcount_no_fte | `emission={"1": 8000.0}, fte={}`           | `modules[1]==8.0` (falls back to emission/1000)       |
| fte_only         | `emission={}, fte={"1": 50.0}`             | `modules={1: 50.0}, total_fte=50.0, total_tonnes=0.0` |

---

### 2b. `compute_results_summary()` — pure, no DB

**File:** `backend/tests/unit/utils/test_compute_results_summary.py`

#### Fixture: realistic multi-module scenario

```python
current_emissions = {
    "1": 5000.0,     # headcount — has FTE, has prev (went down)
    "2": 12000.0,    # travel — has prev (unchanged)
    "4": 8500.0,     # equipment — prev == 0 (div/0 guard)
    "5": None,       # purchases — not validated → skipped
    "7": 3200.0,     # cloud — no prev at all
}
current_fte = {"1": 120.0}
prev_emissions = {"1": 6000.0, "2": 12000.0, "4": 0.0}
co2_per_km_kg = 0.17
headcount_key = "1"
```

**Assertions on `module_results`:**

| module | `total_tonnes` | `total_fte` | `year_comparison_%`       | `equivalent_car_km` | `prev_tonnes` |
| ------ | -------------- | ----------- | ------------------------- | ------------------- | ------------- |
| 1      | `5.0`          | `120.0`     | `-16.67` (5000−6000)/6000 | `5000/0.17`         | `6.0`         |
| 2      | `12.0`         | `None`      | `0.0` (unchanged)         | `12000/0.17`        | `12.0`        |
| 4      | `8.5`          | `None`      | `None` (prev==0, div/0)   | `8500/0.17`         | `0.0`         |
| 5      | —              | —           | —                         | —                   | — (skipped)   |
| 7      | `3.2`          | `None`      | `None` (no prev)          | `3200/0.17`         | `None`        |

**Assertions on `unit_totals`:**

| Field                  | Expected                             |
| ---------------------- | ------------------------------------ |
| `total_tonnes_co2eq`   | `28.7` ((5000+12000+8500+3200)/1000) |
| `total_fte`            | `120.0`                              |
| `tonnes_co2eq_per_fte` | `28.7 / 120.0`                       |
| `equivalent_car_km`    | `28700 / 0.17`                       |
| `prev_total_tonnes`    | `18.0` ((6000+12000+0)/1000)         |
| `year_comparison_%`    | `+59.44` ((28700−18000)/18000×100)   |
| `co2_per_km_kg`        | `0.17`                               |

#### Edge-case tests (targeted)

| ID                      | Input override                           | What it tests                                   |
| ----------------------- | ---------------------------------------- | ----------------------------------------------- |
| empty_current           | `current_emissions={}`                   | `total_tonnes is None` (not `0.0`)              |
| empty_prev              | `prev_emissions={}`                      | `prev_total is None`, `year_comparison is None` |
| prev_all_zero           | `prev_emissions={"1": 0.0, "2": 0.0}`    | `year_comparison is None` (total prev==0)       |
| no_fte                  | `current_fte={}` (no headcount)          | `total_fte is None`, `tonnes_per_fte is None`   |
| fte_zero                | `current_fte={"1": 0.0}`                 | `tonnes_per_fte is None` (div/0)                |
| single_module_decrease  | `curr={"2": 4500.0}, prev={"2": 5000.0}` | `year_comparison == -10.0`                      |
| single_module_full_drop | `curr={"2": 0.0}, prev={"2": 5000.0}`    | `year_comparison == -100.0`                     |

---

### 2c. Repository tests (DB, SQL filtering)

**Add to `test_data_entry_emission_repo.py`:**

#### `get_validated_totals_by_unit()`

| Test                 | Verifies                                    |
| -------------------- | ------------------------------------------- |
| basic                | 1 year, 1 validated module → correct result |
| multi-year           | 2 years → list ordered ASC                  |
| sums modules         | 2 validated modules same year → sum of both |
| excludes IN_PROGRESS | IN_PROGRESS module → not counted            |
| excludes other unit  | 2 units → only the correct unit             |
| no data              | → `[]`                                      |

#### `get_stats_by_carbon_report_id()` (emission repo)

| Test                         | Verifies                           |
| ---------------------------- | ---------------------------------- |
| single validated module      | → `{"module_type_id_str": sum_kg}` |
| multi modules                | 2 validated modules → 2 keys       |
| excludes IN_PROGRESS         | → absent from dict                 |
| excludes other carbon_report | → no leakage between reports       |
| empty                        | → `{}`                             |

**Add to `test_data_entry_repo.py`:**

#### `get_stats_by_carbon_report_id()` (FTE)

| Test                     | Verifies                                     |
| ------------------------ | -------------------------------------------- |
| basic                    | `DataEntry.data["fte"]=25.5` → `{"1": 25.5}` |
| multiple entries         | FTE summed                                   |
| non-validated module     | → `{}`                                       |
| data without `"fte"` key | → absent from result                         |
| empty                    | → `{}`                                       |

---

### 2d. Service tests (orchestration)

**Create `backend/tests/unit/services/test_unit_totals_service.py`:**

| Test                      | Verifies                                                        |
| ------------------------- | --------------------------------------------------------------- |
| returned structure        | keys `{current_emissions, current_fte, prev_emissions}` present |
| no previous report        | `prev_emissions == {}`                                          |
| previous report exists    | `prev_emissions` non-empty                                      |
| `carbon_report` not found | raises `ValueError`                                             |
| non-validated module      | absent from `current_emissions`                                 |
| yearly — basic            | format `[{"year", "kg_co2eq"}]`                                 |
| yearly — empty            | → `[]`                                                          |

---

## Files

| File                                                               | Action                                                                 |
| ------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| `backend/app/utils/report_computations.py`                         | Create with `compute_validated_totals()` + `compute_results_summary()` |
| `backend/app/api/v1/carbon_report_module_stats.py`                 | Refactor routes to call `utils/report_computations`                    |
| `backend/tests/unit/utils/__init__.py`                             | Create (empty)                                                         |
| `backend/tests/unit/utils/test_compute_validated_totals.py`        | Create                                                                 |
| `backend/tests/unit/utils/test_compute_results_summary.py`         | Create                                                                 |
| `backend/tests/unit/repositories/test_data_entry_emission_repo.py` | Add 2 sections                                                         |
| `backend/tests/unit/repositories/test_data_entry_repo.py`          | Add 1 section                                                          |
| `backend/tests/unit/services/test_unit_totals_service.py`          | Create                                                                 |

---

## Run

```bash
cd backend && python -m pytest \
  tests/unit/utils/ \
  tests/unit/services/test_unit_totals_service.py \
  tests/unit/repositories/test_data_entry_emission_repo.py \
  tests/unit/repositories/test_data_entry_repo.py \
  -v
```

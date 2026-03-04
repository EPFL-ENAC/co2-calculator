# Process Emissions Module — Implementation Plan

## Context

Per issue #31 and the committee decision on 19-01-2026, the Infrastructure module is being split. The existing Infrastructure module (ID=3) continues to handle buildings. A **new** "Process Emissions" module (ID=8) is added to estimate greenhouse gas emissions from chemical/physical reactions in the laboratory (CO₂, CH₄, N₂O, refrigerants like SF₆).

**Intended outcome**: Users with `calco2.user.principal` role can enter process gas quantities, get automatic CO₂-eq calculations using IPCC AR6 GWP values, and see results integrated into the Results page Scope 1 breakdown.

---

## Step 1: Backend — New Enums & Constants

### 1.1 Module Type

**`backend/app/models/module_type.py`**

- Add `process_emissions = 8` to `ModuleTypeEnum`
- Add mapping in `MODULE_TYPE_TO_DATA_ENTRY_TYPES`:
  ```python
  ModuleTypeEnum.process_emissions: [DataEntryTypeEnum.process_emission]
  ```

### 1.2 Data Entry Type

**`backend/app/models/data_entry.py`**

- Add `process_emission = 50` to `DataEntryTypeEnum`

### 1.3 Emission Type

**`backend/app/models/data_entry_emission.py`**

- Add `process = 14` to `EmissionTypeEnum`

---

## Step 2: Backend — Module Handler (DTOs + Handler Class)

**`backend/app/schemas/data_entry.py`**

### Response DTO

```python
class ProcessEmissionHandlerResponse(DataEntryResponseGen):
    emitted_gas: str                    # CO2, CH4, N2O, Refrigerants
    sub_category: Optional[str] = None  # SF6, R134a, R410a (only if Refrigerants)
    quantity_kg: int
    kg_co2eq: Optional[float] = None
```

### Create DTO

```python
class ProcessEmissionHandlerCreate(DataEntryCreate):
    emitted_gas: str
    sub_category: Optional[str] = None
    quantity_kg: int

    @field_validator("quantity_kg", mode="after")
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Quantity must be > 0")
        return v
```

### Update DTO

```python
class ProcessEmissionHandlerUpdate(DataEntryUpdate):
    emitted_gas: Optional[str] = None
    sub_category: Optional[str] = None
    quantity_kg: Optional[int] = None

    @field_validator("quantity_kg", mode="after")
    @classmethod
    def validate_quantity(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("Quantity must be > 0")
        return v
```

### Handler Class

```python
class ProcessEmissionModuleHandler(BaseModuleHandler):
    module_type = ModuleTypeEnum.process_emissions
    data_entry_type = DataEntryTypeEnum.process_emission

    create_dto = ProcessEmissionHandlerCreate
    update_dto = ProcessEmissionHandlerUpdate
    response_dto = ProcessEmissionHandlerResponse

    kind_field = "emitted_gas"
    subkind_field = "sub_category"
    require_subkind_for_factor = False  # only Refrigerants have sub_category

    sort_map = {
        "id": DataEntry.id,
        "emitted_gas": Factor.classification["kind"].as_string(),
        "sub_category": Factor.classification["subkind"].as_string(),
        "quantity_kg": DataEntry.data["quantity_kg"].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        "emitted_gas": Factor.classification["kind"].as_string(),
        "sub_category": Factor.classification["subkind"].as_string(),
    }
```

With `to_response()`, `validate_create()`, `validate_update()` following the same pattern as `ExternalCloudModuleHandler`.

---

## Step 3: Backend — Emission Factors (Seed Data)

**New file: `backend/app/seed/seed_process_emission_factors.py`**

GWP factors seeded into the `factors` table:

| Emitted Gas | Kind         | Subkind | GWP (kg CO₂-eq/kg) | Source                         |
| ----------- | ------------ | ------- | ------------------ | ------------------------------ |
| CO₂         | CO2          | `null`  | 1                  | IPCC AR6 2021 (EF 3.1 Simapro) |
| CH₄         | CH4          | `null`  | 27                 | IPCC AR6 2021 (EF 3.1 Simapro) |
| N₂O         | N2O          | `null`  | 273                | IPCC AR6 2021 (EF 3.1 Simapro) |
| SF₆         | Refrigerants | SF6     | 25200              | labo1point5                    |
| R134a       | Refrigerants | R134a   | 1530               | labo1point5                    |
| R410a       | Refrigerants | R410a   | 2088               | labo1point5                    |

Each factor row:

- `data_entry_type_id` = 50 (`process_emission`)
- `classification` = `{"kind": "<Kind>", "subkind": "<Subkind>", "source": "<Source>"}`
- `values` = `{"gwp_kg_co2eq_per_kg": <GWP>}`

Register the seed function in the existing seed runner (follow pattern of other `seed_*.py` files).

---

## Step 4: Backend — Calculation Formula

**`backend/app/services/data_entry_emission_service.py`**

### 4.1 Register Formula

```python
@DataEntryEmissionService.register_formula(DataEntryTypeEnum.process_emission)
async def compute_process_emission(self, data_entry, factors):
    """Emissions_CO2eq = Quantity (kg) * GWP_factor"""
    quantity_kg = data_entry.data.get("quantity_kg", 0)
    if not factors:
        return {"kg_co2eq": None}
    factor = factors[0]
    gwp = factor.values.get("gwp_kg_co2eq_per_kg", 0)
    kg_co2eq = quantity_kg * gwp
    return {"kg_co2eq": kg_co2eq, "gwp_factor": gwp, "quantity_kg": quantity_kg}
```

### 4.2 Update `prepare_create()` Emission Type Resolution

Add case in the emission type resolution block (~line 50-72):

```python
elif data_entry.data_entry_type == DataEntryTypeEnum.process_emission:
    emission_type = EmissionTypeEnum.process
```

Set `subcategory` to the emitted gas name (or sub_category for refrigerants).

---

## Step 5: Backend — Emission Breakdown & Results Integration

**`backend/app/utils/emission_breakdown.py`**

- Add `8: "Processes"` to `MODULE_TYPE_TO_CATEGORY` (line ~19)
- Update `CATEGORY_CHART_KEYS["Processes"]` from `[]` to `["process"]` (line ~93)
- Add `8: "processEmissions"` to `MODULE_TYPE_TO_PER_PERSON_KEY` (line ~56)

The "Processes" category already exists in `MODULE_BREAKDOWN_ORDER` (line 78) — no change needed there.

---

## Step 6: Backend — Permissions

**`backend/app/models/user.py`**

- Add `"modules.process-emissions": {"view": True, "edit": True}` to `calco2.user.principal` role permissions
- Add `"modules.process-emissions": {"view": False, "edit": False}` to `calco2.user.standard` role permissions
  **`backend/app/core/policy.py`**
- Add `"process-emissions": "modules.process-emissions"` to the module permission path map

---

## Step 7: Frontend — Module Registration

### 7.1 Module Constants

**`frontend/src/constant/modules.ts`**

- Add `ProcessEmissions: 'process-emissions'` to `MODULES`
- Add `ProcessEmissions: 'process-emissions-description'` to `MODULES_DESCRIPTIONS`
- Add `process_emission: 50` to `enumSubmodule`
- Add `SUBMODULE_PROCESS_EMISSIONS_TYPES` constant: `{ ProcessEmission: 'process_emission' }`
- Add `ProcessEmissionsSubType` type
- Add `ProcessEmissionsProps` type to `ConditionalSubmoduleProps` union
- Include `ProcessEmissionsSubType` in `AllSubmoduleTypes`

### 7.2 Module Type ID

**`frontend/src/constant/moduleStates.ts`**

- Add `'process-emissions': 8` to `MODULE_TYPE_IDS`

### 7.3 Backend Module Name Mapping

**`frontend/src/constant/modules.ts`** — `getBackendModuleName()`

- Add `[MODULES.ProcessEmissions]: 'process_emissions'`

---

## Step 8: Frontend — Module Config

**New file: `frontend/src/constant/module-config/process-emissions.ts`**

Fields definition:

- `emitted_gas`: select (optionsId: `'kind'`), required, sortable, editableInline
- `sub_category`: select (optionsId: `'subkind'`), conditionalVisibility: show when `emitted_gas === 'Refrigerants'`, required when visible
- `quantity_kg`: number, required, min=1, step=1, integer only
- `kg_co2eq`: number, readOnly, hideIn form, sortable

Module config:

- `formStructure: 'perSubmodule'`
- Single submodule: `process_emission`
- `hasTableAction: true` (edit/delete buttons)
- `numberFormatOptions: { minimumFractionDigits: 1, maximumFractionDigits: 1 }`

**`frontend/src/constant/module-config/index.ts`**

- Import and register: `'process-emissions': processEmissions`

---

## Step 9: Frontend — i18n Translations

**New file: `frontend/src/i18n/process-emissions.ts`**

Key translations (from spec):

| Key                                     | EN                                            | FR                                            |
| --------------------------------------- | --------------------------------------------- | --------------------------------------------- |
| `process-emissions`                     | Process emissions                             | Emissions de procédés                         |
| `process-emissions-description`         | Enter the sources of process gas emissions... | Entrez les sources d'émissions de procédé...  |
| `process-emissions-description-subtext` | This module allows to estimate...             | Ce module permet d'estimer...                 |
| `process-emissions-tooltip`             | The amount of each greenhouse gas...          | La quantité de chaque gaz à effet de serre... |
| `process-emissions.table_title`         | Process emissions                             | Émissions de procédés                         |
| `process-emissions.inputs.emitted_gas`  | Emitted Gas                                   | Gaz émis                                      |
| `process-emissions.inputs.sub_category` | Sub-category                                  | Sous-catégorie                                |
| `process-emissions.inputs.quantity_kg`  | Quantity (kg)                                 | Quantité (kg)                                 |
| `process-emissions.add_button`          | Add an emitted gas                            | Ajouter un gaz émis                           |
| `process-emissions.work_in_progress`    | work in progress, please validate...          | en cours jusqu'à validation                   |

---

## Step 10: Frontend — Permissions & Charts

### 10.1 Permissions

**`frontend/src/utils/permission.ts`**

- Add `[MODULES.ProcessEmissions]: 'modules.process_emissions'` to `getModulePermissionPath()`

### 10.2 Charts — Treemap

**`frontend/src/components/organisms/module/ModuleCharts.vue`**

- Add case for `'process-emissions'` module type
- Use existing `TreeMapModuleChart.vue` component
- Category = Emitted Gas (from module stats)
- No subcategory drill-down (refrigerants shown as their emitted gas name)
- Chart visible only if ≥1 row exists; show empty state otherwise

---

## Step 11: Database Migration

Create an Alembic migration if needed to ensure:

- `carbon_report_modules` table can handle `module_type_id=8`
- Factor seed data is inserted

---

## Verification

1. **Backend unit tests** (`pytest`):
   - `ProcessEmissionModuleHandler` — quantity validation (>0, integer), emitted_gas required
   - `compute_process_emission` — formula correctness (quantity × GWP)
   - Permission tests — principal has access, standard does not

2. **Manual frontend testing**:
   - Navigate to `/en/<unit>/<year>/process-emissions`
   - Add CO₂ entry (qty=100) → verify `kg_co2eq = 100`
   - Add CH₄ entry (qty=10) → verify `kg_co2eq = 270`
   - Add Refrigerant SF₆ (qty=1) → sub_category dropdown appears → `kg_co2eq = 25200`
   - Validate module → total shows in t CO₂-eq
   - Check Results page → "Processes" bar in Scope 1
   - Treemap shows breakdown by emitted gas
   - Login as `calco2.user.standard` → module greyed out, no Edit button

3. **Existing tests**: `npm run test` (frontend), `pytest` (backend) — no regressions

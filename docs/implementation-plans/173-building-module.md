# Plan: Buildings Module (Task 173)

## Context

The Buildings module (infrastructure, `module_type_id=3`) exists only as a skeleton: enum stubs, a minimal frontend config, and is blocked behind `forbiddenModules` in the UI. This plan implements it fully per the success criteria, covering two submodules (Rooms + Energy Combustion), Archibus room lookup, emission calculations, and Results-page 2-bar chart integration.

---

## Key Design Decisions

| Decision               | Choice                                                                                                                                       |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Results page 2 bars    | Bar 1 = "Buildings energy consumption" (Rooms, `emission_type=energy`). Bar 2 = "Energy combustion" (Combustion), replacing "Buildings room" |
| New emission type      | Add `combustion = 15` to `EmissionTypeEnum`                                                                                                  |
| New data entry type    | Add `energy_combustion = 31` to `DataEntryTypeEnum`                                                                                          |
| Rooms emission storage | 1 `DataEntryEmission` per room; `kg_co2eq` = total; `meta` stores per-type kWh + kg breakdown                                                |
| Archibus rooms         | New `ArchibusRoom` DB table; populated via CSV ingestion; dropdowns query this table                                                         |

---

## Backend Changes

### 1. Models

**`/backend/app/models/data_entry_emission.py`**

- Add `combustion = 15` to `EmissionTypeEnum`

**`/backend/app/models/data_entry.py`**

- Add `energy_combustion = 31` to `DataEntryTypeEnum`

**`/backend/app/models/module_type.py`**

- Update `MODULE_TYPE_TO_DATA_ENTRY_TYPES[ModuleTypeEnum.infrastructure]` to include `DataEntryTypeEnum.energy_combustion`

**New: `/backend/app/models/archibus_room.py`**

```python
class ArchibusRoom(SQLModel, table=True):
    __tablename__ = "archibus_rooms"
    id: Optional[int] = Field(default=None, primary_key=True)
    building_name: str       # from "# Bâtiment" column
    building_code: str       # from "CF4 + Sigle" column
    room_code: str           # from "CODE Porte" column
    room_name: str           # display name
    generic_type_din: str    # DIN Sous-type from Archibus
    sia_type: str            # mapped from DIN via DIN_to_SIA table
    surface_m2: float        # from "SURFACE m2" column
```

### 2. Factor Structure

**New seed file: `/backend/seed_data/seed_building_energy_factors.csv`**
Columns: `kind, subkind, heating_kwh_per_m2, cooling_kwh_per_m2, ventilation_kwh_per_m2, lighting_kwh_per_m2`

Stored as `Factor`:

- `emission_type_id = 1` (energy), `data_entry_type_id = 30` (building)
- `classification = {"kind": sia_room_type, "subkind": building_code}`
- `values = {"heating_kwh_per_m2": ..., "cooling_kwh_per_m2": ..., "ventilation_kwh_per_m2": ..., "lighting_kwh_per_m2": ...}`

Electricity emission factor (already exists as `energy_mix` factor, reuse `FactorService.get_electricity_factor()`).

**New seed file: `/backend/seed_data/seed_combustion_factors.csv`**
Columns: `kind, subkind, kg_co2eq_per_unit, unit`

Stored as `Factor`:

- `emission_type_id = 15` (combustion), `data_entry_type_id = 31` (energy_combustion)
- `classification = {"kind": "Gaz naturel"}`
- `values = {"kg_co2eq_per_unit": 0.205, "unit": "kWh"}`

Heating types: Gaz naturel (kWh), Propane (kWh), Mazout (kWh), Biométhane (kWh), Granulés de bois (kg), Plaquettes forestières (kg), Bois bûche (kg)

### 3. Schemas / Handlers

**`/backend/app/schemas/data_entry.py`**

Add `BuildingRoomModuleHandler(BaseModuleHandler, data_entry_type=DataEntryTypeEnum.building)`:

- `kind_field = "sia_type"` (room type for factor lookup)
- `subkind_field = "building_code"`
- `resolve_primary_factor_id`: lookup Factor by `kind=sia_type, subkind=building_code`, fallback to kind-only

Add `EnergyCombustionModuleHandler(BaseModuleHandler, data_entry_type=DataEntryTypeEnum.energy_combustion)`:

- `kind_field = "heating_type"`
- `resolve_primary_factor_id`: lookup Factor by `kind=heating_type`

### 4. Emission Formulas

**`/backend/app/services/data_entry_emission_service.py`**

Update `prepare_create()` to route `building` → `EmissionTypeEnum.energy` and `energy_combustion` → `EmissionTypeEnum.combustion`.

Add `DataEntryTypeEnum.building` to electricity factor fetch (same as equipment types).

```python
@DataEntryEmissionService.register_formula(DataEntryTypeEnum.building)
async def compute_building_room(self, data_entry, factors):
    surface = data_entry.data.get("surface_m2")
    energy_factor = factors[0]   # building kWh/m² factors
    elec_factor = factors[1]     # electricity kgCO2eq/kWh
    kgco2_per_kwh = elec_factor.values["kgco2eq_per_kwh"]
    heating_kwh = energy_factor.values["heating_kwh_per_m2"] * surface
    cooling_kwh  = energy_factor.values["cooling_kwh_per_m2"] * surface
    ventilation_kwh = energy_factor.values["ventilation_kwh_per_m2"] * surface
    lighting_kwh = energy_factor.values["lighting_kwh_per_m2"] * surface
    return {
        "kg_co2eq": (heating_kwh + cooling_kwh + ventilation_kwh + lighting_kwh) * kgco2_per_kwh,
        "heating_kwh": heating_kwh, "cooling_kwh": cooling_kwh,
        "ventilation_kwh": ventilation_kwh, "lighting_kwh": lighting_kwh,
        "heating_kg_co2eq": heating_kwh * kgco2_per_kwh,
        "cooling_kg_co2eq": cooling_kwh * kgco2_per_kwh,
        "ventilation_kg_co2eq": ventilation_kwh * kgco2_per_kwh,
        "lighting_kg_co2eq": lighting_kwh * kgco2_per_kwh,
    }

@DataEntryEmissionService.register_formula(DataEntryTypeEnum.energy_combustion)
async def compute_energy_combustion(self, data_entry, factors):
    quantity = data_entry.data.get("quantity")
    factor = factors[0]
    return {"kg_co2eq": quantity * factor.values["kg_co2eq_per_unit"]}
```

### 5. Emission Breakdown (Results Page Fix)

**`/backend/app/utils/emission_breakdown.py`**

```python
_MODULE_EMISSION_CATEGORY = {
    (3, EmissionTypeEnum.energy):     "Buildings energy consumption",  # Rooms
    (3, EmissionTypeEnum.combustion): "Energy combustion",             # replaces "Buildings room"
}

MODULE_BREAKDOWN_ORDER = [
    "Processes",
    "Buildings energy consumption",
    "Energy combustion",    # replaces "Buildings room"
    "Equipment",
    ...
]

CATEGORY_CHART_KEYS = {
    "Buildings energy consumption": ["energy"],
    "Energy combustion": ["combustion"],   # replaces "Buildings room": ["grey_energy"]
    ...
}
```

### 6. New API Endpoints

**`/backend/app/api/v1/carbon_report_module.py`**

**Archibus rooms lookup:**

```
GET /modules/archibus-rooms?building_code=optional
```

Returns list of buildings (for first dropdown) and rooms filtered by building (for second dropdown).

### 7. Archibus Data Ingestion

**New: `/backend/app/services/data_ingestion/csv_providers/archibus_rooms_csv_provider.py`**

- CSV columns: `building_name`, `building_code`, `room_code`, `room_name`, `generic_type_din`, `sia_type`, `surface_m2`
- DIN → SIA type mapping table (maps Archibus DIN Sous-type to one of 6 SIA room types)
- Upserts into `archibus_rooms` table by (building_code, room_code)

**New: `/backend/seed_data/seed_archibus_rooms.csv`** — sample rooms for dev/test

### 8. Factor Service

**`/backend/app/services/factor_service.py`**

- Add `get_factor(**classification)` wrapper method to expose `repo.get_factor` for flexible classification lookups

### 9. Permissions

`check_module_permission` in `/backend/app/core/policy.py` already maps `"infrastructure"` → `"modules.infrastructure"`. No changes needed.

---

## Frontend Changes

### 10. Module Constants

**`/frontend/src/constant/modules.ts`**

- Replace `Facility: 'facility'` with `EnergyCombustion: 'energy_combustion'` in `SUBMODULE_INFRASTRUCTURE_TYPES`
- Add `energy_combustion: 31` to `enumSubmodule`

### 11. Module Config Rewrite

**`/frontend/src/constant/module-config/infrastructure.ts`** — full rewrite

**Rooms submodule** (`type='building'`):

| Field           | Type   | Behavior                                                                    |
| --------------- | ------ | --------------------------------------------------------------------------- |
| building_name   | select | Mandatory, form only; queries `/archibus-rooms`                             |
| room_name       | select | Mandatory, form only; filtered by selected building                         |
| sia_type        | select | 6 options (Office, Miscels, Laboratories, Archives, Libraries, Auditoriums) |
| surface_m2      | number | Auto-filled from Archibus; read-only                                        |
| heating_kwh     | number | Calculated; read-only; table only                                           |
| cooling_kwh     | number | Calculated; read-only; table only                                           |
| ventilation_kwh | number | Calculated; read-only; table only                                           |
| lighting_kwh    | number | Calculated; read-only; table only                                           |
| kg_co2eq        | number | Calculated, rounded 1 decimal; table only                                   |

Column tooltips for Heating, Cooling, Ventilation, Lighting (i18n keys).

**Energy Combustion submodule** (`type='energy_combustion'`):

| Field        | Type   | Behavior                                        |
| ------------ | ------ | ----------------------------------------------- |
| heating_type | select | 7 options (predefined list)                     |
| unit         | text   | Auto-filled from heating_type; read-only/greyed |
| quantity     | number | Integer > 0; user input                         |
| kg_co2eq     | number | Calculated, rounded 1 decimal; table only       |

Both submodules: sortable, searchable, delete-only (no inline edit). "Add with Note" available (same pattern as Equipment).

### 12. i18n Rewrite

**`/frontend/src/i18n/infrastructure.ts`** — full rewrite with all EN/FR strings per success criteria:

- Module title: EN "Buildings" / FR "Bâtiments"
- Module description (long EN/FR text)
- Total: EN "work in progress, please validate to see the results" / FR "en cours jusqu'à validation"
- Column headers for both submodules (all EN/FR)
- Tooltip content for Heating, Cooling, Ventilation, Lighting columns
- Table/form section titles, (i) tooltip texts
- Dropdown option labels (room types, heating types)
- Chart category/subcategory labels

Add to results i18n: `'Energy combustion': 'charts-energy-combustion-subcategory'` (replaces 'Buildings room').

### 13. Module Page — Enable Infrastructure

**`/frontend/src/pages/app/ModulePage.vue`**

- Remove `MODULES.Infrastructure` from `forbiddenModules` array (lines ~72-76)

### 14. Results Chart Fix

**`/frontend/src/components/charts/results/ModuleCarbonFootprintChart.vue`**

- In `CATEGORY_LABEL_MAP`: replace `'Buildings room': 'charts-building-room-subcategory'` → `'Energy combustion': 'charts-energy-combustion-subcategory'`
- Update the ECharts series config: rename the second buildings series from "Buildings room" to "Energy combustion", map it to the `combustion` chart key (replacing `grey_energy`)
- Replace `grey_energy` with `combustion` in `allValueKeys` and `allStdDevKeys`

---

## Critical Files Summary

| File                                                                               | Change                                                                   |
| ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| `backend/app/models/data_entry_emission.py`                                        | Add `combustion = 15`                                                    |
| `backend/app/models/data_entry.py`                                                 | Add `energy_combustion = 31`                                             |
| `backend/app/models/module_type.py`                                                | Update infrastructure data entry types                                   |
| `backend/app/models/archibus_room.py`                                              | **NEW** — ArchibusRoom table                                             |
| `backend/app/schemas/data_entry.py`                                                | Add BuildingRoomModuleHandler + EnergyCombustionModuleHandler            |
| `backend/app/services/factor_service.py`                                           | Add `get_factor(**classification)` wrapper                               |
| `backend/app/services/data_entry_emission_service.py`                              | Add building + combustion formulas; route emission types                 |
| `backend/app/utils/emission_breakdown.py`                                          | Replace "Buildings room"/grey_energy with "Energy combustion"/combustion |
| `backend/app/api/v1/carbon_report_module.py`                                       | Add archibus-rooms endpoint                                              |
| `backend/seed_data/seed_building_energy_factors.csv`                               | **NEW**                                                                  |
| `backend/seed_data/seed_combustion_factors.csv`                                    | **NEW**                                                                  |
| `backend/seed_data/seed_archibus_rooms.csv`                                        | **NEW**                                                                  |
| `backend/app/services/data_ingestion/csv_providers/archibus_rooms_csv_provider.py` | **NEW**                                                                  |
| `frontend/src/constant/modules.ts`                                                 | Replace Facility with EnergyCombustion submodule type                    |
| `frontend/src/constant/module-config/infrastructure.ts`                            | Full rewrite (2 submodules)                                              |
| `frontend/src/i18n/infrastructure.ts`                                              | Full rewrite (EN/FR per spec)                                            |
| `frontend/src/pages/app/ModulePage.vue`                                            | Remove Infrastructure from forbiddenModules                              |
| `frontend/src/components/charts/results/ModuleCarbonFootprintChart.vue`            | Replace "Buildings room" series with "Energy combustion"                 |
| `frontend/src/i18n/results.ts`                                                     | Add `charts-energy-combustion-subcategory`                               |

---

## Database Migration

A new Alembic migration is needed for:

- `archibus_rooms` table (new)
- No schema changes to `data_entries` or `data_entry_emissions` (use JSON `data` and existing columns)

---

## Verification

1. Seed building factors + combustion factors + sample Archibus rooms
2. Add a room via the form → verify surface auto-fills, kWh columns calculate, kg CO₂-eq is correct
3. Add a combustion entry → verify kg CO₂-eq calculated from quantity × factor
4. Validate the module → verify it appears in Results page with 2 bars: "Buildings energy consumption" + "Energy combustion"
5. Test with `calco2.user.standard` → module should be inaccessible
6. Test `calco2.user.principal` → full edit access
7. Verify bottom navigation arrows and Results button work
8. Confirm "work in progress, please validate" message shows before validation

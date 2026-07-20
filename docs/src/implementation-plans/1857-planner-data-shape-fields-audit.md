---
status: proposed
issue: 1857
last_updated: 2026-07-20
title: "Planner — per-module data-shape & fields audit"
summary: "First-priority audit (gates #1557 F1) comparing each Simulator Plan module's mockup table against the API response shape, recording present fields, gaps, and the corrected reference-year column labels. Purchases excluded."
---

# Planner — per-module data-shape & fields audit

## Problem/Purpose

This audit precedes F1 of the Simulator Plan frontend ([#1557](1557-simulator-plan-frontend.md)):
before the results chart and totals are built, every planner module's table — as drawn in the
[#404](404-simulation-module-plan.md) mockups — must be checked against what the API actually
returns, so gaps are recorded up front rather than discovered mid-build.

It also corrects two mislabels in the #404 mockup. The baseline column reads **"Last year's
tco2eq"** and the slider **"Percentage of last year"**. Per the PO/PM decision of 2026-07-16
both are wrong: it is the **reference year**, not "last year", and the unit is **kgCO₂eq**, not
tonnes.

**This issue is an audit only — it records findings and decisions; it ships no code.** The fixes
it surfaces are follow-up work.

**Scope:** all planner modules **except Purchases** — Headcount, Professional Travel, Process
Emissions, Buildings, Equipment, Research Facilities.

## How the shapes flow (contract surfaces)

- Per-entry lists come from the existing submodule endpoint
  `GET /modules/{unit_id}/{year}/{module_id}/{submodule_id}` with `carbon_project_type=2`
  (Simulator Plan). There is no dedicated planner endpoint yet.
- Per-entry `kg_co2eq` **is** computed per data entry in the repo
  (`backend/app/repositories/data_entry_repo.py` `get_submodule_data`, injected into
  `enriched_data`) and surfaced on most submodule DTOs — in **kg**, not tonnes. A planner
  `tco2eq` column is therefore `kg_co2eq / 1000`.
- Descriptive-field DTOs live in `backend/app/modules/<module>/data_entries.py`. A module DTO only
  serialises the fields it explicitly declares (the base `DataEntryResponseGen` excludes the raw
  `data` dict), so an undeclared computed value is silently dropped.
- On this branch (`feat/1857-…`, off `dev`) the [#1556](1556-simulation-plan-backend.md) backend
  contract **has landed** (commit `7745653d0`). `DataEntryResponseGen`
  (`backend/app/schemas/data_entry.py`) now declares **both** planner fields — `reference_kg_co2eq`
  and `percentage_of_reference_year` — which power the reference column and the slider, and both
  are populated for planner snapshot rows: `reference_kg_co2eq` is injected in
  `data_entry_repo.py` `get_submodule_data` for rows carrying a `source_data_entry_id`, and
  `percentage_of_reference_year` is spread in from `data_entry.data` (seeded to `100` at copy time
  in `simulator_plan_service.py`). Both inherit to every module response DTO.
- Frontend table columns are the submodule's `moduleFields[]` where `hideIn.table` is falsy, plus
  an `action` column (`frontend/src/constant/module-config/*.ts`, `ModuleTable.vue` `qCols`). The
  reference column + slider are _injected_ by `qCols` under `show-reference-columns`, not
  config-declared.

## Verdict summary

- **Descriptive fields:** fully present in the API for every audited module.
- **Current per-entry tco2eq** (`kg_co2eq`): present for every audited module **except
  Headcount** — which by design has no per-entry tco2eq (it is counted by `fte`, the exceptional
  module; **H1**) — and buildings `building_embodied_energy` (outside the drawn tables).
- **Reference-year tco2eq column + % slider:** **available on this branch** — #1556 has landed, so
  `reference_kg_co2eq` + `percentage_of_reference_year` are exposed and populated on every
  prefilled module's response (was gap **R1**, now resolved; one shared backend dependency, not
  per-module).
- **Labels:** "Last year's tco2eq" → **"Reference year kgCO₂eq"**; "Percentage of last year" →
  **"% of reference year"**; drop tonnes for kg.

| Module              | Descriptive fields | Current `kg_co2eq`                     | Reference col + slider         |
| ------------------- | ------------------ | -------------------------------------- | ------------------------------ |
| Headcount           | present            | none — counted by `fte` by design (H1) | not drawn                      |
| Professional Travel | present            | present                                | n/a (empty / Calculator table) |
| Process Emissions   | present            | present                                | available (#1556 landed)       |
| Buildings           | present            | present                                | available (#1556 landed)       |
| Equipment           | present            | present                                | available (#1556 landed)       |
| Research Facilities | present            | present                                | available (#1556 landed)       |

## Per-module audit

### Headcount — Type 1 manual

`backend/app/modules/headcount/data_entries.py`

- Needed table cells: SIUS-code category (row label) + editable `fte`. No tco2eq column drawn.
- API `HeadcountItemResponse`: `name`, `sius_code`, `fte`, `user_institutional_id` — present.
  `HeadCountStudentResponse`: `fte` — present.
- **H1 (by design, not a gap):** headcount has no per-entry `kg_co2eq` — it is the exceptional
  module, counted by `fte` instead of tco2eq, so the DTO correctly omits it and no tco2eq column
  is drawn. Any per-category headcount kg needed for the results chart must come from the module
  aggregate `stats` (keyed by `sius_code`), never from these entries.
- Note: the mockup shows 7 friendly labels (Professor … Other); backend `SIUS_CODE_VALUES` has 8
  codes `{51,52,53,54,56,57,58,59}`. The code→label mapping is a frontend i18n concern, not an API
  gap.

### Professional Travel — Type 3 empty-by-default

`backend/app/modules/professional_travel/data_entries.py`

- Standard Calculator plane/train table, no prefill. The plane/train DTOs carry origin/dest
  `name`+`iata`, `cabin_class`, `number_of_trips`, `departure_date`, `distance_km`,
  `traveler_name`, `kg_co2eq` — all present.
- Note: the traveler category is not modeled server-side, so the traveler column renders `-` in
  the planner (a known #1557 divergence, not an API-field gap for the drawn table).

### Process Emissions — Type 2 prefilled

`backend/app/modules/process_emissions/data_entries.py`

- Needed columns: Emitted Gas | Subcategory | Reference kgCO₂eq | kgCO₂eq | % slider.
- API `ProcessEmissionsHandlerResponse`: `category` (= Emitted Gas), `subcategory`, `quantity`,
  `kg_co2eq` — descriptive + current tco2eq present.
- **R1 (resolved):** reference column (`reference_kg_co2eq`) + slider
  (`percentage_of_reference_year`) are present on this branch via #1556.

### Buildings — Type 2 prefilled

`backend/app/modules/buildings/data_entries.py`

- Needed columns: Building | Room | Room Type | Reference kgCO₂eq | kgCO₂eq | % slider.
- API `BuildingRoomHandlerResponse`: `building_name`, `room_name`, `room_type`, surface/kwh
  fields, `kg_co2eq` — descriptive + current tco2eq present.
- **R1 (resolved)** as above.
- Note: `building_embodied_energy` (32) exposes only `building_name`, **no `kg_co2eq`**; the
  Calculator frontend doesn't show embodied — a decision is needed on whether the planner
  snapshots or shows it. `energy_combustion` (31) has `kg_co2eq` but is outside the drawn rooms
  table.

### Equipment — Type 2 prefilled

`backend/app/modules/equipment/data_entries.py`

- Needed columns: Name | Class | Sub-class | Active usage (hrs/wk) | Standby usage (hrs/wk) |
  Equipment type | kgCO₂eq | % slider.
- API `EquipmentHandlerResponse`: `name`, `equipment_class` (Class), `sub_class`,
  `active_usage_hours_per_week`, `standby_usage_hours_per_week`, `kg_co2eq`
  (+ `active_power_w`/`standby_power_w`) — descriptive + current tco2eq present.
- "Equipment type" (Scientific / IT / Other) is **not a data field** — it is the submodule
  (`data_entry_type_id`, present on the base DTO). Mixing the 3 submodules in one table needs a
  type→label mapping, and IT rows have no `sub_class`.
- **R1 (resolved)** as above.

### Research Facilities — Type 2 prefilled

`backend/app/modules/research_facilities/data_entries.py` (common + animal responses share the
one file: `ResearchFacilitiesCommonHandlerResponse`, `ResearchFacilitiesAnimalHandlerResponse`)

- API common: `researchfacility_name`, `use`, `use_unit`, `kg_co2eq`; animal adds
  `researchfacility_type` — descriptive + current tco2eq present.
- **R1 (resolved)** as above.
- Note: currently **excluded** from Simulator Explore (`getExploreModules` filters
  `MODULES.ResearchFacilities`); the Plan must include it.

## Gaps to carry forward (follow-up, not this issue)

- **~~R1~~ (resolved):** #1556 has landed — `reference_kg_co2eq` + `percentage_of_reference_year`
  are exposed and populated on the planner submodule responses across all four prefilled modules.
  No follow-up.
- **H1 (Headcount) — not a gap:** headcount is counted by `fte`, not tco2eq, so its DTO correctly
  has no per-entry `kg_co2eq`. Results-chart headcount kg (if needed) comes from aggregate `stats`.
- **Buildings embodied:** decide snapshot/display of `building_embodied_energy`.
- **Labels:** apply "Reference year kgCO₂eq" / "% of reference year" (i18n), drop tonnes.

## Out of scope

- Purchases (excluded per request).
- Implementing any DTO / field / i18n change — this issue records the audit only.

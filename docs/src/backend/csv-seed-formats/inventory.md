---
status: delivered
last_updated: 2026-05-05
summary: Per-file column inventory for the seed-data CSVs (factors, data, test).
---

# CSV column inventory

This page lists every column on every file in the seed-data SharePoint mirror. It is the human-curated reference; for parser-level details and idempotency rules, see the [main CSV seed formats page](../csv-seed-formats.md).

When the spec and the parser code disagree, **code wins** and the discrepancy is flagged with `?` and a footnote.

## Factors (`*_factors.csv`)

One row per `(classification, year)` tuple. Required columns come from the corresponding `BaseFactorHandler.create_dto` in `backend/app/modules/<module>/schemas.py`, minus the meta fields declared in `backend/app/schemas/factor.py:11-18`.

| File | Columns |
|---|---|
| `building_energycombustions_factors.csv` | `unit`, `name`, `ef_kg_co2eq_per_unit` |
| `building_rooms_factors.csv` | `building_name`, `room_type`, `heating_kwh_per_square_meter`, `cooling_kwh_per_square_meter`, `ventilation_kwh_per_square_meter`, `lighting_kwh_per_square_meter`, `ef_kg_co2eq_per_kwh`, `energy_type`, `conversion_factor` |
| `equipments_factors.csv` | `equipment_category`[^1], `equipment_class`, `sub_class`, `active_power_w`, `standby_power_w`, `active_usage_hours_per_week`, `standby_usage_hours_per_week`, `ef_kg_co2eq_per_kwh` |
| `external_ai_factors.csv` | `provider`, `usage_type`, `ef_kg_co2eq_per_request` |
| `external_clouds_factors.csv` | `service_type`, `provider`, `currency`, `ef_kg_co2eq_per_currency` |
| `headcount_member_factors.csv` | `headcount_category`, `headcount_class`, `headcount_subclass`, `number_of_unit_per_fte`, `ef_kg_co2eq_per_unit`, `unit` |
| `headcount_students_factors.csv` | `headcount_category`, `headcount_class`, `headcount_subclass`, `number_of_unit_per_fte`, `ef_kg_co2eq_per_unit`, `unit` |
| `processemissions_factors.csv` | `category`, `subcategory`, `unit`, `ef_kg_co2eq_per_unit` |
| `purchases_additional_factors.csv` | `name`, `ef_kg_co2eq_per_kg` |
| `purchases_common_factors.csv` | `currency`, `purchase_category`[^2], `purchase_institutional_code`, `purchase_institutional_description`, `purchase_additional_code`, `ef_kg_co2eq_per_currency` |
| `researchfacilities_animals_factors.csv` | `researchfacility_id`, `researchfacility_name`, `processemissions_share`, `building_energycombustions_share`, `building_rooms_share`, `purchases_common_share`, `purchases_additional_share`, `equipments_share`, `kg_co2eq_sum`[^3], `researchfacility_type`, `total_use`, `use_unit` |
| `researchfacilities_common_factors.csv` | `researchfacility_id`, `researchfacility_name`, `kg_co2eq_sum`, `total_use`, `use_unit` |
| `travel_planes_factors.csv` | `category`, `ef_kg_co2eq_per_km`, `class_adjustement`, `rfi_adjustment`, `min_distance`, `max_distance` |
| `travel_trains_factors.csv` | `country_code`, `ef_kg_co2eq_per_km` |

[^1]: Listed in spec; **not a column on `EquipmentFactorCreate`** in `backend/app/modules/equipment_electric_consumption/schemas.py:267-275`. The string `equipment_category` is `EquipmentModuleHandler.category_field`, used to resolve the `data_entry_type` (it/scientific/other) from the row at parse time, not stored on the factor row.
[^2]: Listed in spec; **not a column on `PurchaseCommonFactorCreate`** in `backend/app/modules/purchase/schemas.py:398-410`. Same shape as `equipment_category`: `purchase_category` is `PurchaseModuleHandler.category_field`, used to resolve the purchase data_entry_type (e.g. `services`, `vehicles`) from the row, not persisted as a factor field.
[^3]: Listed in spec as a single column. **In code (`ResearchFacilitiesAnimalFactorCreate`, `animals_schemas.py:189-206`) the field is split into six per-source columns**: `kg_co2eq_sum_processemissions`, `kg_co2eq_sum_building_energycombustions`, `kg_co2eq_sum_building_rooms`, `kg_co2eq_sum_purchases_common`, `kg_co2eq_sum_purchases_additional`, `kg_co2eq_sum_equipments`. The animal-facility formula sums each `(use / total_use) * source_share * kg_co2eq_sum_<source>` per source. Author the actual CSV with all six.

## Data (`*_data.csv`)

One row per data entry. Common shape: `unit_institutional_id` + handler-specific entity fields + `note` + optional `kg_co2eq` override.

| File | Columns |
|---|---|
| `building_energycombustions_data.csv` | `unit_institutional_id`, `name`, `unit`, `quantity`, `note`, `kg_co2eq` |
| `building_rooms_data.csv` | `unit_institutional_id`, `building_location`[^4], `building_name`, `room_name`, `room_type`, `note`, `kg_co2eq` |
| `equipments_data.csv` | `unit_institutional_id`, `name`, `equipment_class`, `sub_class`, `active_usage_hours_per_week`, `standby_usage_hours_per_week`, `note`, `kg_co2eq` |
| `external_ai_data.csv` | `unit_institutional_id`, `provider`, `usage_type`, `requests_per_user_per_day`, `user_count`, `note`, `kg_co2eq` |
| `external_clouds_data.csv` | `unit_institutional_id`, `service_type`, `provider`, `spent_amount`, `currency`, `note`, `kg_co2eq` |
| `headcount_data.csv`[^5] | `unit_institutional_id`, `name`, `position_title`, `position_category`, `user_institutional_id`, `fte`, `note` |
| `processemissions_data.csv` | `unit_institutional_id`, `category`, `subcategory`, `quantity`, `note`, `kg_co2eq` |
| `purchases_additional_data.csv` | `unit_institutional_id`, `name`, `unit`, `annual_consumption`, `coef_to_kg`, `note`, `kg_co2eq` |
| `purchases_common_data.csv` | `unit_institutional_id`, `name`, `supplier`, `quantity`, `total_spent_amount`, `currency`, `purchase_institutional_code`, `purchase_institutional_description`, `purchase_additional_code`, `note`, `kg_co2eq` |
| `researchfacilities_animals_data.csv` | `unit_institutional_id`, `researchfacility_id`, `researchfacility_name`, `researchfacility_type`, `use`, `use_unit`, `note`, `kg_co2eq` |
| `researchfacilities_common_data.csv` | `unit_institutional_id`, `researchfacility_id`, `researchfacility_name`, `use`, `use_unit`, `note`, `kg_co2eq` |
| `travel_planes_data.csv` | `unit_institutional_id`, `origin_iata`, `destination_iata`, `user_institutional_id`, `departure_date`, `number_of_trips`, `cabin_class`, `note`, `kg_co2eq` |
| `travel_trains_data.csv` | `unit_institutional_id`, `origin_name`, `destination_name`, `user_institutional_id`, `departure_date`, `number_of_trips`, `cabin_class`, `note`, `kg_co2eq` |

[^4]: Listed in spec; **not a column on `BuildingRoomHandlerCreate`** in `backend/app/modules/buildings/schemas.py:90-103`. The handler accepts only `building_name, room_name, room_type, note`. Extra columns are silently ignored by the provider, so `building_location` may be present in source files but is not parsed or stored.
[^5]: A single `headcount_data.csv` covers two handlers — `HeadCountCreate` (member rows) and `HeadCountStudentCreate` (student rows: only `fte` is required, all other member fields ignored). The provider resolves the per-row handler from the `position_category` value or factor lookup. See `backend/app/modules/headcount/schemas.py:54-97`.

## Test (`*_test.csv`)

A `*_test.csv` is a `*_data.csv` minus the operator-supplied columns: drop `unit_institutional_id` (the unit is supplied at upload time via the API), drop `kg_co2eq` (these fixtures are meant to exercise the compute path).

| File | Columns |
|---|---|
| `building_energycombustions_test.csv` | `name`, `unit`, `quantity`, `note` |
| `building_rooms_test.csv` | `building_location`[^4], `building_name`, `room_name`, `room_type`, `note` |
| `equipments_IT_test.csv` | `name`, `equipment_class`, `sub_class`, `active_usage_hours_per_week`, `standby_usage_hours_per_week`, `note` |
| `equipments_other_test.csv` | same as `equipments_IT_test.csv` |
| `equipments_scientific_test.csv` | same as `equipments_IT_test.csv` |
| `external_ai_test.csv` | `provider`, `usage_type`, `requests_per_user_per_day`, `user_count`, `note` |
| `external_clouds_test.csv` | `service_type`, `provider`, `spent_amount`, `currency`, `note` |
| `headcount_test.csv` | `name`, `position_title`, `position_category`, `user_institutional_id`, `fte`, `note` |
| `processemissions_test.csv` | `category`, `subcategory`, `quantity`, `note` |
| `purchases_additional_test.csv` | `name`, `unit`, `annual_consumption`, `coef_to_kg`, `note` |
| `purchases_<sub>_test.csv` (7 sub-types) | `name`, `supplier`, `quantity`, `total_spent_amount`, `currency`, `purchase_institutional_code`, `purchase_institutional_description`, `purchase_additional_code`, `note` |
| `researchfacilities_animals_test.csv` | `researchfacility_id`, `researchfacility_name`, `researchfacility_type`, `use`, `use_unit`, `note` |
| `researchfacilities_common_test.csv` | `researchfacility_id`, `researchfacility_name`, `use`, `use_unit`, `note` |
| `travel_planes_test.csv` | `origin_iata`, `destination_iata`, `user_institutional_id`, `departure_date`, `number_of_trips`, `cabin_class`, `note` |
| `travel_trains_test.csv` | `origin_name`, `destination_name`, `user_institutional_id`, `departure_date`, `number_of_trips`, `cabin_class`, `note` |

The seven `purchases_<sub>_test.csv` sub-types (`scientific_equipment`, `it_equipment`, `consumable_accessories`, `biological_chemical_gaseous_product`, `services`, `vehicles`, `other_purchases`) all share the same column set; they map to distinct `data_entry_type` values via `PurchaseModuleHandler.registration_keys` (`backend/app/modules/purchase/schemas.py:152-160`).

Note: as of today, these `*_test.csv` files live only in the SharePoint mirror — none are tracked in git. The in-repo equivalents under `backend/tests/integration/data_ingestion/fixtures/` follow the same column conventions and are the canonical reference for shape and edge cases.

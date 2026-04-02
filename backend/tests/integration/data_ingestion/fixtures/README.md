# CSV Test Fixtures Reference

## MODULE_PER_YEAR Format

Used for: headcount, travel, buildings, purchases, research facilities, etc.

**Key Characteristic**: Includes `unit_institutional_id` column to identify which unit the data belongs to.

### Valid Example (valid_module_per_year.csv)

```csv
unit_institutional_id,name,position_title,position_category,user_institutional_id,fte,note
UNIT001,John Doe,Professor,professor,UID001,1.0,
UNIT002,Jane Smith,Post-doctoral researcher,postdoctoral_assistant,UID002,0.5,
```

**Required Fields** (for headcount member):

- `unit_institutional_id` - Unit identifier
- `name` - Person name
- `position_category` - Must be one of: professor, scientific_collaborator, postdoctoral_assistant, doctoral_assistant, trainee, technical_administrative_staff, student, other

**Optional Fields**:

- `position_title` - Job title
- `user_institutional_id` - User ID (digits only)
- `fte` - Full-time equivalent (0.0 to 1.0)
- `note` - Additional notes

### Missing Required Columns (missing_required_columns.csv)

```csv
unit_institutional_id,name,position_title
UNIT001,John Doe,Professor
```

Missing: `position_category` (required)

### With Extra Columns (with_extra_columns.csv)

```csv
unit_institutional_id,name,position_title,position_category,user_institutional_id,fte,note,extra_column_ignored
UNIT001,John Doe,Professor,professor,UID001,1.0,,extra_value
```

Extra columns are silently ignored by the CSV provider.

### Empty CSV (empty.csv)

```csv
unit_institutional_id,name,position_title,position_category,user_institutional_id,fte,note
```

Headers only, no data rows → Returns error: "Wrong CSV format or encoding: CSV file is empty"

---

## MODULE_UNIT_SPECIFIC Format

Used for: equipment, external AI, external clouds, etc.

**Key Characteristic**: Does NOT include `unit_institutional_id` - the `carbon_report_module_id` is passed in the API request config.

### Valid Example (valid_module_unit_specific.csv)

```csv
name,equipment_class,sub_class,active_usage_hours_per_week,standby_usage_hours_per_week,note,kg_co2eq
Thermostat Numérique,Agitator / Incubator,CO2 incubators,12,150,Test equipment,
ECRAN EIZO FLEXSCAN,Monitors,,8,160,Another equipment,
```

**Required Fields** (for equipment):

- `name` - Equipment name
- `equipment_class` - Equipment classification (for factor matching)

**Optional Fields**:

- `sub_class` - Sub-classification
- `active_usage_hours_per_week` - Must be 0-168
- `standby_usage_hours_per_week` - Must be 0-168
- `note` - Additional notes
- `kg_co2eq` - Pre-computed emissions (optional)

**Validation Rules**:

- `active_usage_hours_per_week + standby_usage_hours_per_week <= 168`

---

## Source Tracking

The CSV upload automatically sets the `source` field based on entity type:

- **MODULE_PER_YEAR**: `source = DataEntrySourceEnum.CSV_MODULE_PER_YEAR` (value: 1)
- **MODULE_UNIT_SPECIFIC**: `source = DataEntrySourceEnum.CSV_MODULE_UNIT_SPECIFIC` (value: 2)

Human entries have `source = DataEntrySourceEnum.USER_MANUAL` (value: 0) and are **never** overwritten by CSV uploads.

---

## Test Coverage

| Fixture File                     | Test Scenario               | Expected Result                                                           |
| -------------------------------- | --------------------------- | ------------------------------------------------------------------------- |
| `valid_module_per_year.csv`      | MODULE_PER_YEAR new rows    | Rows inserted successfully                                                |
| `valid_module_unit_specific.csv` | MODULE_UNIT_SPECIFIC append | Rows appended successfully                                                |
| `with_extra_columns.csv`         | Extra columns               | Success, extra columns ignored                                            |
| `missing_required_columns.csv`   | Missing required fields     | Error: "Wrong CSV format or encoding: CSV is missing required columns..." |
| `empty.csv`                      | Empty CSV (headers only)    | Error: "Wrong CSV format or encoding: CSV file is empty"                  |
| `not_a_csv.txt`                  | Non-CSV file                | Error during CSV parsing                                                  |

---

## Real-World Examples from Seed Data

See `backend/seed_data/` for production CSV examples:

- `headcount_data.csv` - MODULE_PER_YEAR format
- `equipments_data.csv` - MODULE_PER_YEAR format (has unit_institutional_id)
- `travel_planes_data.csv` - MODULE_PER_YEAR format
- `building_rooms_data.csv` - MODULE_PER_YEAR format

Note: The seed CSV files all use MODULE_PER_YEAR format (with `unit_institutional_id`). MODULE_UNIT_SPECIFIC uploads are typically done via API with `carbon_report_module_id` in the request config.

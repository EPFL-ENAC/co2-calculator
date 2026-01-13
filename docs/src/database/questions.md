User: Here is my plan/todo

1. we need to fix the relationship definition in **init**.py and the erd

ok, have a look at the erd, and tell me what relationship are missing based on column name ?
I'm thinking department_id for instance

2. we need to review again the relation between emission_types and factors (ask me questions and let's iterate) (maybe we need to have factors 1-to-1 emission_types and also data_entry_emissions 1-to-1 emission_types for groupby/aggregate)

3. We then need to review all the erd table one by one, column by column and decide if it's necessary or not

GitHub Copilot: Research SQLAlchemy models and relationships

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/__init__.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/carbon_report.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/factor.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/department.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/emission_type.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/data_entry.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/data_entry_emission.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/data_entry_type.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/module_type.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/user.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/department_user.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/emission_factor.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/audit.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/equipment.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/headcount.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/inventory.py)

Based on the research, here's my analysis of the missing relationships:

## Plan: ERD Relationship Analysis & Schema Review

This plan addresses the three areas you outlined: fixing missing relationships, reviewing the factors/emission_types relationship, and conducting a column-by-column schema audit.

---

### 1. Missing Relationships in ERD (based on FK columns)

**Comparing your ERD with the actual models, these relationships are MISSING from the ERD diagram:**

| FK Column       | From Table       | To Table      | Status in ERD             |
| --------------- | ---------------- | ------------- | ------------------------- |
| `department_id` | `carbon_reports` | `departments` | ❌ **Missing**            |
| `department_id` | `equipment`      | `departments` | ❌ Missing (legacy model) |
| `department_id` | `headcounts`     | `departments` | ❌ Missing (legacy model) |
| `department_id` | `inventories`    | `departments` | ❌ Missing (legacy model) |

**The ERD already shows these relationships correctly:**

- ✅ `carbon_report_modules` → `carbon_reports`
- ✅ `carbon_report_modules` → `module_types`
- ✅ `data_entries` → `carbon_report_modules`
- ✅ `data_entries` → `data_entry_types`
- ✅ `data_entry_emissions` → `data_entries`
- ✅ `data_entry_emissions` → `emission_types`
- ✅ `data_entry_emissions` → `factors`
- ✅ `factors` → `data_entry_types`
- ✅ `department_users` → `departments`
- ✅ `department_users` → `users`

**Priority fix needed:** Add `departments ||--}o carbon_reports : department_id` to the ERD.

---

### 2. Question: `factors` ↔ `emission_types` Relationship

Looking at your data-flow doc, I have clarifying questions:

**Current design:**

- `factors.factor_family` = `"power"` | `"headcount"` | `"emission"` | etc. (string, not FK)
- `data_entry_emissions.emission_type_id` → FK to `emission_types`

**Question A:** Should a `factor` know which `emission_type(s)` it produces?

- **Headcount factor** → produces 4 emission types (food, waste, transport, grey_energy)
- **Power factor** → produces 1 emission type (energy)
- **Emission factor** (energy mix) → is itself an emission type conversion

Options:

1. **No FK needed** — The mapping is implicit in code (HeadcountStrategy knows to create 4 rows)
2. **Add `emission_type_id` FK to `factors`** — 1:1 for most factors, but headcount would need 4 factor rows
3. **Add a junction table `factor_emission_types`** — Many-to-many, explicit mapping

**Question B:** For aggregation/groupby queries, is `data_entry_emissions.emission_type_id` sufficient?

Example query: "Total kg CO2eq by emission_type for department X in 2025" — this should work with current design.

---

### 3. Further Considerations

1. **Legacy tables:** Should `equipment`, `headcounts`, `inventories`, `inventory_modules`, `power_factors`, `emission_factors` be removed from the schema since you now use the generic `data_entries` + `factors` approach?
2. **`module_type_id` on `factors`:** Currently factors link to `data_entry_type_id` — should there also be a direct FK to `module_types` for easier querying?
3. **Do you want me to proceed with the column-by-column review** of each table after we settle the factors/emission_types relationship?

User: 1) also, infer relationship based on column name ? when necessary, we probably 2) question A: I'm thinking yes; four headcount we have 4 factors, one for each emission type it'll be pretty straighforward: just kgco2eq_per_fte for waste, food, transport, gray_energy --> read the frontend and come up with a normalize table for factor family ; I 'm okay with 4 rows for headcount; FK (option 2)

Question B: for now yes

3. 1. yes; 2: not for now; 3: yes

GitHub Copilot: Research frontend factor families

Read [](file:///Users/guilbert/works/git/github/co2-calculator/frontend/src/constant)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/frontend/src/types.ts)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/frontend/src/constant/modules.ts)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/frontend/src/constant/moduleConfig.ts)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/frontend/src/constant/module-config)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/seed_emission_factors.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/seed_headcount.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/factor.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/frontend/src/constant/module-config/my-lab.ts)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/emission_type.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/emission_factor.py)

Searched for regex `factor_family|headcount.*kg|food_kg|waste_kg|transport_kg|grey_energy`, 20 results

Read [](file:///Users/guilbert/works/git/github/co2-calculator/docs/src/database/data-flow.md#150-150), lines 150 to 350

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/tests/unit/services/test_factor_service.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/alembic/versions/2026_01_09_1530-002_seed_reference_data.py)

Searched for regex `factor_family.*flight|flight.*factor|distance_band|cabin_class`, 10 results

Read [](file:///Users/guilbert/works/git/github/co2-calculator/frontend/src/constant/module-config/infrastructure.ts)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/frontend/src/constant/module-config/equipment-electric-consumption.ts)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/frontend/src/constant/module-config/professional-travel.ts)

Searched for regex `kg_per_km|kg_co2eq_per|emission.*factor.*value`, 20 results

Read [](file:///Users/guilbert/works/git/github/co2-calculator/docs/src/database/data-flow.md#730-730), lines 730 to 766

Searched for files matching `**/table_power.csv`, no matches

Searched for files matching `**/*.csv`, no matches

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/api/v1)

Searched for text `table_power.csv`, 6 results

Searched for regex `EMISSION_FACTOR_SWISS_MIX|0\.128|0\.012`, 16 results

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/core/config.py#50-50), lines 50 to 80

Excellent! Now I have a clearer picture. Based on the research, let me present the updated plan:

## Plan: ERD & Schema Normalization

Normalizing the `factors` table to have a 1:1 relationship with `emission_types`, fixing missing ERD relationships, and removing legacy tables.

---

### Steps

1. **Add missing ERD relationship:** Add `departments ||--}o carbon_reports : department_id` to erd.md and define the SQLAlchemy relationship in **init**.py.

2. **Add `emission_type_id` FK to `factors` table:** Modify `Factor` model to include `emission_type_id: int = Field(foreign_key="emission_types.id")` — each factor row now produces exactly one emission type.

3. **Restructure headcount factors:** Split the current single headcount factor (with 4 values) into **4 separate factor rows**:
   - `food` factor → emission_type_id=2, values: `{"kg_co2eq_per_fte": 420}`
   - `waste` factor → emission_type_id=3, values: `{"kg_co2eq_per_fte": 65}`
   - `transport` factor → emission_type_id=4, values: `{"kg_co2eq_per_fte": 350}`
   - `grey_energy` factor → emission_type_id=5, values: `{"kg_co2eq_per_fte": 120}`

4. **Update ERD with new relationship:** Add `emission_types ||--}o factors : emission_type_id` to the ERD diagram.

5. **Remove legacy tables from models:** Delete `Equipment`, `EquipmentEmission`, `HeadCount`, `Inventory`, `InventoryModule`, `PowerFactor`, `EmissionFactor` models from **init**.py.

6. **Proceed with column-by-column table review** (next iteration).

---

### Further Considerations

1. **Normalized factor `values` schema:** With 1:1 emission_type, should we normalize `values` keys?
   - **Option A:** Generic `{"value": 420, "unit": "kg_co2eq_per_fte"}` for all factors
   - **Option B:** Keep factor-family-specific keys (`active_power_w`, `kg_co2eq_per_fte`, etc.) for clarity
   - **Recommendation:** Option B — keeps domain semantics clear

2. **Migration strategy:** Do you want a single Alembic migration or split (schema change + data migration)?

3. **HeadcountCalculationStrategy update:** The strategy will need to fetch 4 factors (one per emission_type) instead of parsing a single JSON — confirm this is acceptable?

User: Start implementation

GitHub Copilot: Created 6 todos

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/__init__.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/generate_mermaid_erd.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/factor.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/carbon_report.py)

Now let me check the other model files that need relationships:

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/data_entry_emission.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/emission_type.py)

Now let me check which legacy models exist to remove:

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models)

Let me check which files should be removed and understand their contents:

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/equipment.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/headcount.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/inventory.py)

Read [](file:///Users/guilbert/works/git/github/co2-calculator/backend/app/models/emission_factor.py)

Now I have all the information needed. Let me implement the changes:

Using "Multi-Replace String in Files"

```

```

```

```

Starting: _Add emission_types → factors relationship to ERD_ (3/6)

Now let me update the **init**.py to remove legacy models and add the missing relationships:

Using "Replace String in File"

```

```

Using "Replace String in File"

```

```

Using "Replace String in File"

```

```

Starting: _Update data-flow.md with new schema_ (6/6)

Now let's regenerate the ERD to verify the relationships are correct:

Ran terminal command: cd /Users/guilbert/works/git/github/co2-calculator/backend && python -m app.generate_mermaid_erd 2>&1

Configuring a Python Environment
Completed with input: {
"resourcePath": "/Users/guilbert/works/git/github/co2-calculator/backend"
}

Creating a Virtual Environment
Completed with input: {
"resourcePath": "/Users/guilbert/works/git/github/co2-calculator/backend"
}

Made changes.

User: I'm using uv please use it also

GitHub Copilot: Ran terminal command: uv run python -m app.generate_mermaid_erd 2>&1

The ERD now shows all the relationships correctly. Let me update the ERD documentation file:

Read [](file:///Users/guilbert/works/git/github/co2-calculator/docs/src/database/erd.md)

Using "Replace String in File"

```

```

Created 6 todos

Done! Here's a summary of what was implemented:

## Changes Made

### 1. Fixed Missing Relationships

**ERD now shows these new relationships:**

- `departments ||--}o carbon_reports : department_id` ✅
- `emission_types ||--}o factors : emission_type_id` ✅

### 2. Added `emission_type_id` FK to `factors` table

factor.py — Each factor now has a 1:1 relationship with an emission type. Headcount will have 4 separate factor rows (one per emission type: food, waste, transport, grey_energy).

### 3. Fixed `department_id` FK in `carbon_reports`

carbon_report.py — Added proper `foreign_key="departments.id"` declaration.

### 4. Removed Legacy Models from **init**.py

Removed:

- `EmissionFactor`, `EmissionFactorBase` (deprecated)
- `PowerFactor`, `PowerFactorBase` (deprecated)
- `Equipment`, `EquipmentBase` (legacy)
- `HeadCount`, `HeadCountBase`, `HeadCountCreate`, `HeadCountRead`, `HeadCountUpdate` (legacy)

### 5. Added Missing SQLAlchemy Relationships

New bidirectional relationships in **init**.py:

- `Department ↔ CarbonReport`
- `ModuleType ↔ CarbonReportModule`
- `EmissionType ↔ DataEntryEmission`
- `EmissionType ↔ Factor`
- `DataEntryType ↔ Factor`
- `Factor ↔ DataEntryEmission`

---

**Next step:** Do you want to proceed with the column-by-column table review, or update the `data-flow.md` documentation with the new factor structure (headcount now has 4 factor rows)?

Made changes.

User: yes

GitHub Copilot: Created 2 todos

Let me go through each table column-by-column. I'll present them for your review:

---

## Table Review: Column-by-Column Analysis

### 1. `emission_types` ✅ Looks good

| Column        | Type       | Necessary? | Notes                                      |
| ------------- | ---------- | ---------- | ------------------------------------------ |
| `id`          | INTEGER PK | ✅ Yes     | Auto-increment PK                          |
| `code`        | VARCHAR UK | ✅ Yes     | Unique identifier (energy, food, waste...) |
| `label`       | VARCHAR    | ✅ Yes     | Human-readable display                     |
| `unit`        | VARCHAR    | ✅ Yes     | Always `kg_co2eq` but good for flexibility |
| `description` | VARCHAR    | ✅ Yes     | Documentation                              |

**Verdict:** Keep as-is.

---

### 2. `factors` — Questions

| Column               | Type       | Necessary?      | Notes                                                   |
| -------------------- | ---------- | --------------- | ------------------------------------------------------- |
| `id`                 | INTEGER PK | ✅ Yes          |                                                         |
| `factor_family`      | VARCHAR    | ✅ Yes          | power, headcount, flight, building, emission            |
| `emission_type_id`   | INTEGER FK | ✅ Yes          | **NEW** - 1:1 with emission_type                        |
| `data_entry_type_id` | INTEGER FK | ✅ Yes          | Links to submodule (scientific, student...)             |
| `classification`     | JSON       | ⚠️ **Question** | Equipment needs `{class, sub_class}`, headcount doesn't |
| `values`             | JSON       | ✅ Yes          | Factor coefficients                                     |
| `value_units`        | JSON       | ⚠️ **Question** | Redundant if units are standardized?                    |
| `version`            | INTEGER    | ⚠️ **Question** | We have `document_versions` — do we need this?          |
| `valid_from`         | TIMESTAMP  | ⚠️ **Question** | Versioning via `document_versions`?                     |
| `valid_to`           | TIMESTAMP  | ⚠️ **Question** | Versioning via `document_versions`?                     |
| `source`             | VARCHAR    | ✅ Yes          | Data provenance                                         |
| `meta`               | JSON       | ✅ Yes          | Flexible metadata                                       |

**Questions for you:**

1. **`classification`** — Keep for equipment lookup, but headcount doesn't use it. Keep empty `{}` for headcount?
2. **`value_units`** — Remove? Units could be implicit or in `meta`.
3. **`version`, `valid_from`, `valid_to`** — These duplicate `document_versions`. Remove them and rely solely on audit table?

---

### 3. `carbon_reports` ✅ Looks good

| Column          | Type       | Necessary? |
| --------------- | ---------- | ---------- |
| `id`            | INTEGER PK | ✅ Yes     |
| `year`          | INTEGER    | ✅ Yes     |
| `department_id` | INTEGER FK | ✅ Yes     |

**Verdict:** Keep as-is. Simple and clean.

---

### 4. `carbon_report_modules` ✅ Looks good

| Column             | Type       | Necessary? |
| ------------------ | ---------- | ---------- | ----------------------------------------- |
| `id`               | INTEGER PK | ✅ Yes     |
| `carbon_report_id` | INTEGER FK | ✅ Yes     |
| `module_type_id`   | INTEGER FK | ✅ Yes     |
| `status`           | INTEGER    | ✅ Yes     | 0=not_started, 1=in_progress, 2=validated |

**Verdict:** Keep as-is.

---

### 5. `data_entries` ✅ Looks good

| Column                    | Type       | Necessary? |
| ------------------------- | ---------- | ---------- | ---------------------------------- |
| `id`                      | INTEGER PK | ✅ Yes     |
| `carbon_report_module_id` | INTEGER FK | ✅ Yes     |
| `data_entry_type_id`      | INTEGER FK | ✅ Yes     | Submodule (scientific, student...) |
| `data`                    | JSON       | ✅ Yes     | Flexible data storage              |

**Verdict:** Keep as-is.

---

### 6. `data_entry_emissions` ✅ Looks good

| Column             | Type       | Necessary?      |
| ------------------ | ---------- | --------------- | ----------------------------------- |
| `id`               | INTEGER PK | ✅ Yes          |
| `data_entry_id`    | INTEGER FK | ✅ Yes          |
| `emission_type_id` | INTEGER FK | ✅ Yes          |
| `factor_id`        | INTEGER FK | ✅ Yes          |
| `kg_co2eq`         | FLOAT      | ✅ Yes          |
| `meta`             | JSON       | ✅ Yes          | Calculation inputs for traceability |
| `formula_version`  | VARCHAR    | ⚠️ **Question** | Move to `meta`?                     |
| `computed_at`      | TIMESTAMP  | ✅ Yes          |
| `is_current`       | BOOLEAN    | ✅ Yes          |

**Question:** Should `formula_version` be in `meta` instead of a separate column?

---

### 7. `data_entry_types` ✅ Looks good

| Column           | Type       | Necessary? |
| ---------------- | ---------- | ---------- | ------------------------------ |
| `id`             | INTEGER PK | ✅ Yes     |
| `name`           | VARCHAR    | ✅ Yes     | scientific, student, member... |
| `description`    | VARCHAR    | ✅ Yes     |
| `module_type_id` | INTEGER FK | ✅ Yes     |

**Verdict:** Keep as-is.

---

### 8. `departments` — Questions

| Column                    | Type       | Necessary?      | Notes                                 |
| ------------------------- | ---------- | --------------- | ------------------------------------- |
| `id`                      | INTEGER PK | ✅ Yes          |                                       |
| `code`                    | VARCHAR UK | ✅ Yes          | LCBM, LPBS...                         |
| `name`                    | VARCHAR    | ✅ Yes          |                                       |
| `cf`                      | VARCHAR    | ⚠️ **Question** | Cost factor code — needed?            |
| `provider`                | VARCHAR    | ⚠️ **Question** | Auth provider — needed on department? |
| `principal_user_id`       | VARCHAR    | ✅ Yes          | SCIPER of PI                          |
| `principal_user_function` | VARCHAR    | ⚠️ **Question** | Denormalized from users?              |
| `principal_user_name`     | VARCHAR    | ⚠️ **Question** | Denormalized from users?              |
| `principal_user_email`    | VARCHAR    | ⚠️ **Question** | Denormalized from users?              |
| `affiliations`            | JSON       | ✅ Yes          | ["SB", "ISIC"]                        |
| `visibility`              | VARCHAR    | ✅ Yes          | public, private, department           |
| `old_id`                  | VARCHAR    | ⚠️ **Question** | Migration artifact — keep?            |

**Questions:**

1. **`cf`** — Is cost factor still used?
2. **`provider`** — Why on department? Should be on user only?
3. **`principal_user_*`** — These are denormalized. Could use FK to `users.id` instead?
4. **`old_id`** — Legacy migration field. Remove after migration complete?

---

### 9. `department_users` ✅ Looks good

| Column          | Type       | Necessary? |
| --------------- | ---------- | ---------- |
| `id`            | INTEGER PK | ✅ Yes     |
| `department_id` | INTEGER FK | ✅ Yes     |
| `user_id`       | INTEGER FK | ✅ Yes     |
| `role`          | VARCHAR    | ✅ Yes     |

**Verdict:** Keep as-is.

---

### 10. `module_types` ✅ Looks good

| Column        | Type       | Necessary? |
| ------------- | ---------- | ---------- | ----------------------------------------- |
| `id`          | INTEGER PK | ✅ Yes     |
| `name`        | VARCHAR UK | ✅ Yes     | my-lab, equipment-electric-consumption... |
| `description` | VARCHAR    | ✅ Yes     |

**Verdict:** Keep as-is.

---

### 11. `users` — Questions

| Column         | Type       | Necessary?      | Notes                             |
| -------------- | ---------- | --------------- | --------------------------------- |
| `id`           | INTEGER PK | ✅ Yes          |                                   |
| `sciper`       | VARCHAR UK | ✅ Yes          | EPFL unique ID                    |
| `email`        | VARCHAR UK | ✅ Yes          |                                   |
| `display_name` | VARCHAR    | ✅ Yes          |                                   |
| `provider`     | VARCHAR    | ✅ Yes          | Auth provider                     |
| `roles_raw`    | JSON       | ⚠️ **Question** | Raw roles from provider — needed? |
| `is_active`    | BOOLEAN    | ✅ Yes          |                                   |
| `last_login`   | DATETIME   | ✅ Yes          |                                   |
| `old_id`       | VARCHAR    | ⚠️ **Question** | Migration artifact — keep?        |

**Questions:**

1. **`roles_raw`** — Is this used or just for debugging?
2. **`old_id`** — Legacy migration field. Remove?

---

### 12. `document_versions` ✅ Looks good

| Column          | Type       | Necessary? |
| --------------- | ---------- | ---------- |
| `id`            | INTEGER PK | ✅ Yes     |
| `entity_type`   | VARCHAR    | ✅ Yes     |
| `entity_id`     | INTEGER    | ✅ Yes     |
| `version`       | INTEGER    | ✅ Yes     |
| `is_current`    | BOOLEAN    | ✅ Yes     |
| `data_snapshot` | JSON       | ✅ Yes     |
| `data_diff`     | JSON       | ✅ Yes     |
| `change_type`   | VARCHAR    | ✅ Yes     |
| `change_reason` | VARCHAR    | ✅ Yes     |
| `changed_by`    | VARCHAR    | ✅ Yes     |
| `changed_at`    | DATETIME   | ✅ Yes     |
| `previous_hash` | VARCHAR    | ✅ Yes     |
| `current_hash`  | VARCHAR    | ✅ Yes     |

**Verdict:** Keep as-is.

---

## Summary of Questions for Your Decision

1. **`factors.value_units`** — Remove? (units in meta or implicit)
2. **`factors.version`, `valid_from`, `valid_to`** — Remove? (use document_versions only)
3. **`data_entry_emissions.formula_version`** — Move to `meta`?
4. **`departments.cf`** — Still needed?
5. **`departments.provider`** — Remove? (should be on user only)
6. **`departments.principal_user_*`** — Keep denormalized or use FK?
7. **`departments.old_id`**, **`users.old_id`** — Remove after migration?
8. **`users.roles_raw`** — Still needed?

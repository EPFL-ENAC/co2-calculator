# CSV Data Entry Type Resolution Refactoring

## Summary

Refactored CSV data ingestion to use module-specific category columns instead of the generic `data_entry_type` column. This makes the CSV ingestion more explicit and type-safe per module.

## Changes Made

### 1. Added `category_field` to `BaseModuleHandler`

**File:** `backend/app/schemas/data_entry.py`

Added a new optional field to declare which CSV column determines the `data_entry_type` for each module:

```python
category_field: Optional[str] = None
```

### 2. Updated Module Handlers

The following module handlers now declare their category fields:

- **Equipment** (`backend/app/modules/equipment_electric_consumption/schemas.py`):
  - `category_field: str = "equipment_category"`
  - Maps values like "scientific", "it", "other" to corresponding `DataEntryTypeEnum`

- **Purchases** (`backend/app/modules/purchase/schemas.py`):
  - `category_field: str = "purchase_category"`
  - Maps values like "scientific_equipment", "it_equipment", etc.

- **Headcount** (`backend/app/modules/headcount/schemas.py`):
  - No `category_field` needed - data.csv files are already split by `data_entry_type`
  - Note: `headcount_category` column exists but serves a different purpose (determines EmissionType within member/student entries: food, waste, commuting, grey_energy)

### 3. Added Helper Method to BaseCSVProvider

**File:** `backend/app/services/data_ingestion/base_csv_provider.py`

Added `_resolve_data_entry_type_from_category()` static method that:

- Extracts the category value from the row using the handler's `category_field`
- Maps the category string to `DataEntryTypeEnum`
- Handles errors gracefully with proper error reporting

### 4. Updated CSV Provider Resolution Logic

**Files:**

- `backend/app/services/data_ingestion/csv_providers/module_unit_specific.py`
- `backend/app/services/data_ingestion/csv_providers/module_per_year.py`
- `backend/app/services/data_ingestion/base_factor_csv_provider.py`

Updated `_resolve_handler_and_validate()` methods to use a **simplified resolution strategy**:

1. **Priority 1:** Configured `data_entry_type_id` from job config
2. **Priority 2:** Module-specific category column (e.g., `equipment_category`)
3. **Priority 3:** Determine from factor (for MODULE_PER_YEAR only)

No backward compatibility is maintained for deprecated `data_entry_type` columns.

## Benefits

1. **Explicit Type Safety:** Each module declares its category column, making the code more self-documenting
2. **Better Validation:** Category-specific validation errors are clearer (e.g., "Invalid equipment_category: xyz")
3. **Cleaner Code:** Removed legacy fallback logic, simpler resolution path
4. **Maintainable:** Centralized resolution logic in base classes reduces code duplication

## Testing

The implementation requires CSV files to use the new category columns or have `data_entry_type_id` configured in the job config.

## Migration Path

For CSV imports, use module-specific category columns:

- Equipment CSVs: Use `equipment_category` column
- Purchase CSVs: Use `purchase_category` column

Alternatively, configure `data_entry_type_id` in the job config for single-type imports.

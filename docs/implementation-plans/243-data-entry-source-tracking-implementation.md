# Source Tracking Implementation Summary

## Overview

Implemented source tracking for data entries to enable selective deletion based on upload method. This solves the problem of having three different CSV upload paths with different deletion behaviors:

1. **MODULE_UNIT_SPECIFIC**: Add data entries (no deletion)
2. **MODULE_PER_YEAR**: Replace/add ONLY data uploaded through module_per_year
3. **FACTORS**: Drop all corresponding factors and insert

## Changes Made

### 1. Database Migration

**File**: `backend/alembic/versions/2026_03_18_1400-2026031801_add_source_tracking_to_data_entries.py`

Added two columns to `data_entries` table:

- `source` (Integer, nullable) - DataEntrySourceEnum value
- `created_by_id` (Integer, nullable) - user.id or data_ingestion_job.id

Both columns are indexed for query performance.

### 2. Model Updates

**File**: `backend/app/models/data_entry.py`

Added `DataEntrySourceEnum` enum with values:

- `USER_MANUAL = 0` - Manual entry via UI
- `CSV_MODULE_PER_YEAR = 1` - CSV upload via module_per_year provider
- `CSV_MODULE_UNIT_SPECIFIC = 2` - CSV upload via module_unit_specific provider
- `API_MODULE_PER_YEAR = 3` - API upload for module per year
- `API_MODULE_UNIT_SPECIFIC = 4` - API upload for unit specific module
- `EXTERNAL_INTEGRATION = 5` - Third-party integration or import

Added fields to `DataEntry` model:

- `source: Optional[DataEntrySourceEnum]`
- `created_by_id: Optional[int]`

### 3. Repository Layer

**File**: `backend/app/repositories/data_entry_repo.py`

Added method:

```python
async def bulk_delete_by_source(
    self,
    carbon_report_module_id: int,
    data_entry_type_id: DataEntryTypeEnum,
    source: DataEntrySourceEnum,
) -> None
```

### 4. Service Layer

**File**: `backend/app/services/data_entry_service.py`

Updated `bulk_create()` to accept:

- `source: Optional[DataEntrySourceEnum]`
- `created_by_id: Optional[int]`

Added new method:

```python
async def bulk_delete_by_source(
    self,
    carbon_report_module_id: int,
    data_entry_type_id: DataEntryTypeEnum,
    source: DataEntrySourceEnum,
    user: Optional[UserRead] = None,
    request_context: Optional[dict] = None,
    background_tasks: Optional[BackgroundTasks] = None,
) -> None
```

### 5. CSV Provider Base Class

**File**: `backend/app/services/data_ingestion/base_csv_provider.py`

Added source tracking to `_process_batch()`:

- Automatically determines source from `entity_type`
- Passes `source` and `created_by_id` to `bulk_create()`

Added deletion logic for MODULE_PER_YEAR:

- `_delete_existing_entries_for_module_per_year()` method
- Called before processing new CSV data
- Deletes only entries with `source = CSV_MODULE_PER_YEAR`
- Preserves manual entries and unit-specific uploads

Added helper method:

```python
def _get_source_from_entity_type(self) -> DataEntrySourceEnum | None
```

## Behavior

### MODULE_PER_YEAR CSV Upload

1. **Before processing**: Delete all existing entries where `source = CSV_MODULE_PER_YEAR` for affected modules
2. **During processing**: Set `source = CSV_MODULE_PER_YEAR`, `created_by_id = job.id`
3. **Result**: Replaces only previous CSV uploads, preserves manual entries

### MODULE_UNIT_SPECIFIC CSV Upload

1. **No deletion**: Entries are added without removing existing data
2. **During processing**: Set `source = CSV_MODULE_UNIT_SPECIFIC`, `created_by_id = job.id`
3. **Result**: Cumulative additions

### FACTORS CSV Upload

1. **Unchanged**: Still uses `bulk_delete_by_data_entry_type()` to drop all factors
2. **No source tracking needed**: Factors are reference data, not user data

## Query Examples

```sql
-- Get all entries from a specific CSV job
SELECT * FROM data_entries WHERE created_by_id = 123;

-- Get all module_per_year CSV entries for a module
SELECT * FROM data_entries
WHERE carbon_report_module_id = 456
  AND source = 1;  -- CSV_MODULE_PER_YEAR

-- Count by source
SELECT source, COUNT(*)
FROM data_entries
GROUP BY source;

-- Get entries with unknown source (legacy data)
SELECT * FROM data_entries WHERE source IS NULL;
```

## Testing

Migration applied successfully:

```bash
make db-migrate
# Output: Running upgrade 0367f025e8d8 -> 2026031801, add source tracking to data_entries
```

Model fields verified:

```python
'source' in DataEntry.model_fields  # True
'created_by_id' in DataEntry.model_fields  # True
```

Code formatting passed:

```bash
make format
# Output: 244 files left unchanged, All checks passed!
```

## Migration Notes

- Existing data has `NULL` for both `source` and `created_by_id`
- This is intentional - we don't guess the origin of legacy data
- New uploads will have proper source tracking
- Queries should handle `NULL` values for backward compatibility

## Future Enhancements

1. **API Upload Tracking**: Update API endpoints to set `source = API_*` and `created_by_id = user.id`
2. **UI Exposure**: Add source fields to admin/backoffice API responses
3. **Audit Enhancement**: Include source in audit trail snapshots
4. **Data Migration**: Optionally backfill source for existing data if audit logs provide clues

## Files Modified

1. `backend/alembic/versions/2026_03_18_1400-2026031801_add_source_tracking_to_data_entries.py` (NEW)
2. `backend/app/models/data_entry.py`
3. `backend/app/repositories/data_entry_repo.py`
4. `backend/app/services/data_entry_service.py`
5. `backend/app/services/data_ingestion/base_csv_provider.py`

## Success Criteria

✅ Migration runs successfully  
✅ Model fields added and accessible  
✅ Repository method for source-based deletion  
✅ Service layer supports source tracking  
✅ CSV providers set source automatically  
✅ MODULE_PER_YEAR deletes only same-source entries  
✅ MODULE_UNIT_SPECIFIC adds without deletion  
✅ Code passes formatting checks  
✅ All lint errors resolved

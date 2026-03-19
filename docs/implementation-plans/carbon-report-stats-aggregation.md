# Carbon Report Stats Aggregation Implementation

## Overview

Added a `stats` column to the `CarbonReport` model that aggregates emission statistics from all child `CarbonReportModule` records, similar to the existing module-level stats.

## Changes Made

### 1. Database Schema (`backend/app/models/carbon_report.py`)

- Added `stats` field to `CarbonReportBase` model
  - Type: `Optional[dict]` with JSON column
  - Stores aggregated emission statistics from all child modules
  - Format: `{scope1, scope2, scope3, total, by_emission_type, computed_at, entry_count}`
- Added `last_updated` field to track when report data changed
  - Type: `Optional[int]` (epoch seconds)
  - Updated automatically when child modules change

### 2. API Schema (`backend/app/schemas/carbon_report.py`)

- Added `stats: Optional[dict]` to `CarbonReportRead` schema
- Added `stats: Optional[dict]` to `CarbonReportModuleRead` schema
- Both fields are included in API responses

### 3. Carbon Report Service (`backend/app/services/carbon_report_service.py`)

- Added `recompute_report_stats(carbon_report_id: int)` method
  - Aggregates stats from all child modules
  - Sums scope1, scope2, scope3, total across modules
  - Merges `by_emission_type` dicts (grouping by emission_type_id)
  - Sums `entry_count` across all modules
  - Updates `computed_at` timestamp
  - Persists to `CarbonReport.stats` column

### 4. Carbon Report Module Service (`backend/app/services/carbon_report_module_service.py`)

- Modified `recompute_stats()` to trigger parent report stats recomputation
  - After updating module stats, calls `CarbonReportService.recompute_report_stats()`
  - Ensures report-level stats stay synchronized with module stats
  - Happens in the same transaction

### 5. CSV Data Ingestion (`backend/app/services/data_ingestion/base_csv_provider.py`)

- Updated `_recompute_module_stats()` method
  - Now recomputes stats for both modules AND parent carbon reports
  - For MODULE_PER_YEAR: recomputes stats for each affected carbon report
  - For MODULE_UNIT_SPECIFIC: recomputes stats for the parent carbon report
  - Ensures CSV ingestion updates both module and report stats

### 6. Database Migration

- Created Alembic migration: `01b45209983b_add_stats_and_last_updated_to_carbon_reports.py`
- Adds `stats` column (JSON, nullable) to `carbon_reports` table
- Adds `last_updated` column (Integer, nullable) to `carbon_reports` table
- Migration successfully applied to database

## Stats Format

The `stats` JSON structure for CarbonReport:

```json
{
  "scope1": 1234.56,
  "scope2": 789.01,
  "scope3": 2345.67,
  "total": 4369.24,
  "by_emission_type": {
    "1": 500.0,
    "2": 734.56,
    "3": 1000.0,
    "...": "..."
  },
  "computed_at": "2026-03-19T15:19:29.330566+00:00",
  "entry_count": 42
}
```

## Benefits

1. **Performance**: Pre-computed stats avoid on-the-fly aggregation queries
2. **Consistency**: Report stats automatically update when modules change
3. **Frontend Optimization**: Quick access to report-level totals without complex joins
4. **Data Integrity**: Single source of truth for emission aggregations

## Testing Recommendations

1. Test module stats recomputation triggers report stats update
2. Verify CSV ingestion updates both module and report stats
3. Check API response includes stats in `CarbonReportRead`
4. Validate stats aggregation:
   - Scope totals match sum of module scopes
   - `entry_count` matches sum of module entry_counts
   - `by_emission_type` properly merges across modules
5. Test with empty modules (no data entries)
6. Test with partial data (some modules have data, others don't)

## Migration Path

- Existing reports will have `stats=null` until first recomputation
- No backward compatibility maintained for old format
- To backfill historical data:
  1. Run a script to iterate over all carbon reports
  2. Call `CarbonReportService.recompute_report_stats(report_id)` for each
  3. This will populate stats for all existing reports

## Related Files

- `backend/app/models/carbon_report.py`
- `backend/app/schemas/carbon_report.py`
- `backend/app/services/carbon_report_service.py`
- `backend/app/services/carbon_report_module_service.py`
- `backend/app/services/data_ingestion/base_csv_provider.py`
- `backend/alembic/versions/2026_03_19_1519-01b45209983b_add_stats_and_last_updated_to_carbon_.py`

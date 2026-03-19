# Carbon Report Stats and Progress Tracking Implementation

## Overview

Added comprehensive tracking to the `CarbonReport` model:

1. **stats**: Aggregated emission statistics from all child `CarbonReportModule` records
2. **completion_progress**: String showing completed modules (e.g., "5/7")
3. **overall_status**: Inferred status from child modules (NOT_STARTED, IN_PROGRESS, VALIDATED)

## Changes Made

### 1. Database Schema (`backend/app/models/carbon_report.py`)

- Added `stats` field to `CarbonReportBase` model
  - Type: `Optional[dict]` with JSON column
  - Stores aggregated emission statistics from all child modules
  - Format: `{scope1, scope2, scope3, total, by_emission_type, computed_at, entry_count}`
- Added `last_updated` field to track when report data changed
  - Type: `Optional[int]` (epoch seconds)
  - Updated automatically when child modules change
- Added `completion_progress` field to track module completion
  - Type: `Optional[str]` (e.g., "5/7")
  - Shows how many modules are validated vs total modules
- Added `overall_status` field to track report completion status
  - Type: `int` (ModuleStatus enum: 0=NOT_STARTED, 1=IN_PROGRESS, 2=VALIDATED)
  - Inferred from child module statuses:
    - NOT_STARTED: No modules validated
    - IN_PROGRESS: Some modules validated but not all
    - VALIDATED: All modules validated

### 2. API Schema (`backend/app/schemas/carbon_report.py`)

- Added `stats: Optional[dict]` to `CarbonReportRead` schema
- Added `completion_progress: Optional[str]` to `CarbonReportRead` schema
- Added `overall_status: int` to `CarbonReportRead` schema
- Added `stats: Optional[dict]` to `CarbonReportModuleRead` schema
- All fields are included in API responses

### 3. Carbon Report Service (`backend/app/services/carbon_report_service.py`)

- Added `recompute_report_stats(carbon_report_id: int)` method
  - Aggregates stats from all child modules
  - Sums scope1, scope2, scope3, total across modules
  - Merges `by_emission_type` dicts (grouping by emission_type_id)
  - Sums `entry_count` across all modules
  - Updates `computed_at` timestamp
  - Persists to `CarbonReport.stats` column
  - Automatically calls `recompute_report_progress()` after updating stats

- Added `recompute_report_progress(carbon_report_id: int)` method
  - Counts validated modules vs total modules
  - Builds completion_progress string (e.g., "5/7")
  - Determines overall_status:
    - NOT_STARTED if completed_modules == 0
    - VALIDATED if completed_modules == total_modules
    - IN_PROGRESS otherwise
  - Persists to `CarbonReport.completion_progress` and `CarbonReport.overall_status`

### 4. Carbon Report Module Service (`backend/app/services/carbon_report_module_service.py`)

- Modified `recompute_stats()` to trigger parent report stats recomputation
  - After updating module stats, calls `CarbonReportService.recompute_report_stats()`
  - This automatically triggers progress recomputation as well
  - Ensures report-level stats and progress stay synchronized with module stats
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
- Adds `completion_progress` column (String(20), nullable) to `carbon_reports` table
- Adds `overall_status` column (Integer, not null, default=0) to `carbon_reports` table
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

## Completion Progress Format

The `completion_progress` string format:

```
"5/7"
```

Where:

- First number: Count of modules with VALIDATED status
- Second number: Total number of modules (typically 7)

## Overall Status Logic

The `overall_status` is determined by:

```python
if completed_modules == 0:
    overall_status = ModuleStatus.NOT_STARTED  # 0
elif completed_modules == total_modules:
    overall_status = ModuleStatus.VALIDATED    # 2
else:
    overall_status = ModuleStatus.IN_PROGRESS  # 1
```

## Benefits

1. **Performance**: Pre-computed stats avoid on-the-fly aggregation queries
2. **Visibility**: Users can see completion progress at a glance (e.g., "5/7")
3. **Status Tracking**: Overall report status automatically reflects module completion
4. **Consistency**: Report stats and progress automatically update when modules change
5. **Frontend Optimization**: Quick access to report-level totals without complex joins
6. **Data Integrity**: Single source of truth for emission aggregations and progress

## Testing Recommendations

1. Test module stats recomputation triggers report stats update
2. Verify completion_progress updates when module status changes
3. Validate overall_status logic:
   - All modules NOT_STARTED → overall_status = NOT_STARTED
   - Some modules VALIDATED → overall_status = IN_PROGRESS
   - All modules VALIDATED → overall_status = VALIDATED
4. Verify CSV ingestion updates both module and report stats
5. Check API response includes stats, completion_progress, and overall_status
6. Validate stats aggregation:
   - Scope totals match sum of module scopes
   - `entry_count` matches sum of module entry_counts
   - `by_emission_type` properly merges across modules
7. Test with empty modules (no data entries)
8. Test with partial data (some modules have data, others don't)

## Migration Path

- Existing reports will have:
  - `stats=null` until first recomputation
  - `completion_progress=null` until first recomputation
  - `overall_status=0` (NOT_STARTED) by default
- No backward compatibility maintained for old format
- To backfill historical data:
  1. Run a script to iterate over all carbon reports
  2. Call `CarbonReportService.recompute_report_stats(report_id)` for each
  3. This will populate stats, completion_progress, and overall_status

## Related Files

- `backend/app/models/carbon_report.py`
- `backend/app/schemas/carbon_report.py`
- `backend/app/services/carbon_report_service.py`
- `backend/app/services/carbon_report_module_service.py`
- `backend/app/services/data_ingestion/base_csv_provider.py`
- `backend/alembic/versions/2026_03_19_1519-01b45209983b_add_stats_and_last_updated_to_carbon_.py`

## Next Steps (Not Implemented)

1. **Update carbon_report_module endpoints**: Ensure create/update/delete operations in the API trigger report stats/progress recomputation
2. **Add endpoint for manual recomputation**: Create admin endpoint to manually trigger stats/progress recomputation for backfilling
3. **Frontend integration**: Update frontend to display completion_progress and overall_status in report views
4. **Notifications**: Consider adding notifications when report reaches 100% completion

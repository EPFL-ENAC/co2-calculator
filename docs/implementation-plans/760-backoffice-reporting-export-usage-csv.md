# 📄 PRD 1 — Usage CSV (`usage.csv`)

## 1. Objective

Provide a dataset that tracks the **status and progress of each module** for every carbon report.

This dataset is intended for:

- monitoring completion
- identifying gaps in data collection
- operational dashboards

THE CSV results should look like this

report_id
year
unit_id
module_name
module_stat last_updated

---

## 2. Scope

- One row per **(report_id × module_type_id)**
- Covers all modules defined in `ModuleTypeEnum`
- Includes status and last update timestamp

---

## 3. Data Sources

- `carbon_reports`
- `carbon_report_modules`

---

## 4. Data Model

### Granularity

- 1 row = 1 report × 1 module

### Columns

| db column     | csv Column            | Type      | Description                        |
| ------------- | --------------------- | --------- | ---------------------------------- |
| id            | report_id             | integer   | `carbon_reports.id`                |
| year          | year                  | string    | reporting year (2026)              |
| unit_id       | unit_institutional_id | string    | unit identifier (cost center)      |
| module_name   | module_name           | text      | mapped from `module_type_id`       |
| module_status | module_status         | text      | status of the module (cf \*A)      |
| last_updated  | last_updated          | timestamp | last update of the module (cf \*B) |

- (\*A) status of module is 0,1,2 but _MUST_ display Not Started In Progress, Completed --> create an enum in DB or map to facilitate SQL)
- (\*B) date is "2026-03-25T16:23:54.601649+00:00" in stats.computed_at, so that's a problem we should have a 'last_updated' field as Date not null (currently it's null), and in the csv we should have a csv/excell compatible date format like: 2026-03-25

- example of carbon_reports table

```csv
"year"	"unit_id"	"id"	"last_updated"	"stats"	"completion_progress"	"overall_status"
2025	2011	1		"{""scope1"": 0.0, ""scope2"": 0.0, ""scope3"": 96982.92000000001, ""total"": 96982.92000000001, ""by_emission_type"": {""10000"": 27750.0, ""20000"": 827.3199999999999, ""30000"": 68405.6}, ""computed_at"": ""2026-03-30T07:53:04.029432+00:00"", ""entry_count"": 8}"	"0/8"	0
```

- example of carbon_report_modules table

```csv
"module_type_id"	"status"	"carbon_report_id"	"id"	"last_updated"	"stats"
1	0	125	993		"{""scope1"": 0.0, ""scope2"": 0.0, ""scope3"": 81255.95999999999, ""total"": 81255.95999999999, ""by_emission_type"": {""10000"": 23250.0, ""20000"": 693.16, ""30000"": 57312.79999999999}, ""computed_at"": ""2026-03-25T16:23:54.601649+00:00"", ""entry_count"": 8}"
```

---

## 5. Mapping Logic

### module_type_id → module_name

| ID  | Name                           |
| --- | ------------------------------ |
| 1   | headcount                      |
| 2   | professional_travel            |
| 3   | buildings                      |
| 4   | equipment_electric_consumption |
| 5   | purchase                       |
| 6   | research_facilities            |
| 7   | external_cloud_and_ai          |
| 8   | process_emissions              |

---

## 6. SQL Specification

```sql
SELECT
    cr.id AS report_id,
    cr.year,
    cr.unit_id,

    CASE crm.module_type_id
        WHEN 1 THEN 'headcount'
        WHEN 2 THEN 'professional_travel'
        WHEN 3 THEN 'buildings'
        WHEN 4 THEN 'equipment_electric_consumption'
        WHEN 5 THEN 'purchase'
        WHEN 6 THEN 'research_facilities'
        WHEN 7 THEN 'external_cloud_and_ai'
        WHEN 8 THEN 'process_emissions'
    END AS module_name,

    crm.status AS module_status,
    crm.last_updated

FROM carbon_reports cr
JOIN carbon_report_modules crm
    ON crm.carbon_report_id = cr.id

ORDER BY cr.id, crm.module_type_id;
```

---

## 7. Output

- File: `usage.csv`
- Format: CSV
- Sorted by `(report_id, module_type_id)`

---

## 8. Constraints

- All modules must be included, even if status is NULL
- No aggregation
- No filtering by year unless specified externally

---

## Improvements

- Replace `CASE` with a `module_type_mapping` table
- don't forget about completion_progress, overall_status
  - Add completion percentage per report
  - Add derived status (e.g. completed / incomplete)

## Implementation Plan — Back-office Reporting

### data generation first

Now I have a much better understanding of the existing seed data infrastructure! Looking at the existing seed files in `backend/app/seed/`, I can see there's already a well-structured approach for generating test data using Faker and structured seed scripts.

Based on what I've learned from the existing code and your requirements, here's my refined plan:

## Refined Data Generation Plan

### Phase 1: Enhance Existing Seed Infrastructure

1. **Modify `populate_fake_data.py`** to generate:
   - 3,000 units (instead of 10,000)
   - 10,000 users (instead of 40,000)
   - Proper relationships between units and users
   - Realistic roles distribution

2. **Create new seed scripts** for the additional data:
   - `seed_carbon_reports.py` - Generate 9,000 carbon reports (3 per unit for 2023-2025)
   - `seed_carbon_report_modules.py` - Generate carbon report modules for all module types
   - `seed_factors.py` - Generate additional random factors for all data entry types
   - `seed_data_entries.py` - Generate data entries and corresponding emissions

### Phase 2: Leverage Existing Patterns

3. **Follow existing patterns** from the seed files:
   - Use `seed_helper.py` functions for common operations
   - Implement batch processing for large datasets
   - Use proper service layers for data creation
   - Maintain referential integrity with foreign keys

### Phase 3: Implementation Details

4. **Units and Users Generation** (Modified `populate_fake_data.py`):
   - Generate 3,000 realistic units with proper provider codes
   - Generate 10,000 users with appropriate roles
   - Distribute users across units (3-15 users per unit)
   - Assign principal investigators to units

5. **Carbon Reports Generation** (`seed_carbon_reports.py`):
   - For each unit, create 3 carbon reports (2023, 2024, 2025)
   - Total: 9,000 carbon reports

6. **Carbon Report Modules Generation** (`seed_carbon_report_modules.py`):
   - For each carbon report, create modules for all 9 module types
   - Total: 81,000 carbon report modules

7. **Factors Generation** (`seed_factors.py`):
   - Generate random factors for all data entry types
   - Cover all emission types
   - Include both conversion and calculation factors

8. **Data Entries and Emissions Generation** (`seed_data_entries.py`):
   - For each carbon report module, generate ~100 data entries
   - For each data entry, generate corresponding emissions
   - Total: ~8.1 million data entries and emissions

This approach leverages the existing infrastructure while scaling it to meet your requirements. Would you like me to proceed with implementing this plan? I'll need to toggle to Act mode to create the actual seed scripts.

### Mental model first

The feature is essentially: **filters → query → table + exports**. Everything else is cosmetic. Keep that thread in mind when you feel lost.

---

## Phase 1 — Backend

### 1.1 Data model / queries

Figure out what you already have and what's missing. You need to be able to answer:

- For a given unit + year(s): what is the validation status of each module, and the global completion status?
- For a given unit: who is the principal user (from ACCRED), what is the last update date, what is the total carbon footprint?
- What is the affiliation hierarchy? (EPFL → Faculty/VP → Institut → Unit level 4)

**Deliverable:** a single query (or composable query builder) that takes `{years[], unit_ids[], validation_statuses[], module_statuses[]}` and returns the full row data for the table. Everything else — aggregations, exports — derives from this.

### 1.2 Access control

Two roles to enforce server-side on every endpoint:

- `calco2.backoffice.metier` → scoped to their perimeter from ACCRED
- `calco2.superadmin` → no scope restriction

Implement this as middleware/guard you can reuse. Don't scatter it.

### 1.3 Filter endpoints

- `GET /reporting/filters/years` — available years
- `GET /reporting/filters/units` — units within caller's perimeter
- `GET /reporting/filters/affiliations` — faculty/VP/institut tree

These can be simple and cheap. They just populate the UI dropdowns.

### 1.4 Table endpoint

`POST /reporting/units` with body `{ years, unit_ids, validation_statuses, module_statuses, page, page_size, sort_by, sort_dir }`

Returns paginated rows with all columns: validation status, unit, affiliation, principal user, last update, extremely high value, total carbon footprint.

### 1.5 Export endpoints

Four export types, but start with the two that have a real spec:

1. **Usage exports** (`usage_per_school_{YYYY}.csv` + `usage_raw_data_{YYYY}.csv`) — these are well-defined, do these first
2. **Results export** — one row per unit, one column per module
3. **Combined** — merge of 1+2, do last, it's just glue
4. **Detailed** — defer until @guilbep takes a pass

Generate as streams if the dataset is large. Return a ZIP when multi-file.

---

## Phase 2 — Frontend

Only start this once Phase 1.4 is working and tested.

### 2.1 Filter panel

Build as a standalone component that emits a filter state object. Each filter: multi-select, select-all by default, search inside, select all / unselect all toggle. Wire to table + export. This is the most complex UI piece — isolate it.

### 2.2 Units table

Standard paginated sortable table consuming Phase 1.4. Columns in the order specified. The eye icon opens the existing Results page — just a link, should be trivial.

### 2.3 Export button

Rename to `Export data`. Dropdown with the 4 export types. Fires the right endpoint with current filter state. Download the ZIP/CSV response.

### 2.4 Stat boxes

`Usage Statistics` and `Aggregated Results` are placeholders (#461, #460). Drop empty cards with a title and move on.

---

## What to ignore for now

- Outliers column → explicitly removed from spec
- Detailed export → spec not finalized
- Stat boxes → placeholders only
- Institut rows in usage CSV → marked 🚧, confirm scope before building

---

## Suggested order of tickets

1. Data query + access control guard
2. Filter endpoints
3. Table endpoint (+ pagination/sort)
4. Usage CSV exports
5. Results CSV export
6. Frontend: filter panel
7. Frontend: table
8. Frontend: export button
9. Frontend: stat box placeholders
10. Combined export (last, trivial once 4+5 exist)

# Optimization

You don’t have a Python problem.

You have a **“scan 8M rows + spill to disk + aggregate everything before filtering”** problem.

Execution time: **~6.4s**
I/O: **2.3 GB read**, **521 MB written**, heavy temp spill.

The bottleneck is 100% here:

```
Seq Scan data_entry_emissions (8,096,731 rows)
Seq Scan data_entries (8,096,731 rows)
Hash Right Join
HashAggregate (81k rows)
CTE Scan (materialized, spilled)
```

You're aggregating the _entire history of emissions_ before filtering by year.

---

# 🔥 The Core Issue

This line is killing you:

```sql
WITH module_totals AS (
   ...
   FROM carbon_report_modules
   LEFT JOIN data_entries
   LEFT JOIN data_entry_emissions
   GROUP BY ...
)
```

That CTE:

- Reads **ALL 8M emissions**
- Joins ALL entries
- Aggregates ALL modules
- Only afterwards do you filter:

```sql
WHERE carbon_reports.year = 2025
```

So Postgres does 6 seconds of work to compute data you don’t even need.

---

# ✅ First Rule: Filter Early

Move the `year = 2025` filter inside the CTE.

Rewrite like this:

```sql
WITH filtered_reports AS (
    SELECT id
    FROM carbon_reports
    WHERE year = 2025
),
module_totals AS (
    SELECT
        m.id AS module_id,
        m.carbon_report_id,
        m.module_type_id,
        m.status,
        max(e.updated_at) AS updated_at,
        sum(coalesce(em.kg_co2eq, 0) / 1000.0) AS tco2_total
    FROM carbon_report_modules m
    JOIN filtered_reports fr
        ON fr.id = m.carbon_report_id
    LEFT JOIN data_entries e
        ON e.carbon_report_module_id = m.id
    LEFT JOIN data_entry_emissions em
        ON em.data_entry_id = e.id
    GROUP BY
        m.id, m.carbon_report_id, m.module_type_id, m.status
)
```

Now:

- You only aggregate modules belonging to 2025 reports
- You avoid touching irrelevant modules
- You drastically reduce hash join size

This alone can cut execution time by 60–80%.

---

# ✅ Second: Add Missing Indexes

You absolutely need these:

```sql
CREATE INDEX idx_carbon_reports_year
ON carbon_reports(year);

CREATE INDEX idx_carbon_report_modules_report
ON carbon_report_modules(carbon_report_id);

CREATE INDEX idx_data_entries_module
ON data_entries(carbon_report_module_id);

CREATE INDEX idx_data_entry_emissions_entry
ON data_entry_emissions(data_entry_id);
```

Without those, you're forcing sequential scans on 8M rows.

---

# ⚠️ Third: The CTE is Materialized

From the plan:

```
CTE Scan on module_totals
Storage: Disk
```

It is fully materialized and spilled.

In Postgres 12+, CTEs are optimization fences unless `NOT MATERIALIZED`.

Change:

```sql
WITH module_totals AS MATERIALIZED (
```

to

```sql
WITH module_totals AS NOT MATERIALIZED (
```

Or better: inline it as a subquery.

---

# 🚀 The Real Performance Upgrade (Denormalization)

Right now you recompute:

```
sum(kg_co2eq) per module
```

Every time.

That is expensive.

You should store:

### Option A — Store on `carbon_report_modules`

Add column:

```
tco2_total
last_updated_at
```

Update it:

- via trigger on `data_entry_emissions`
- or during emission calculation

Then your query becomes:

```sql
SELECT ...
FROM carbon_report_modules
JOIN carbon_reports
WHERE year = 2025
GROUP BY ...
```

No more 8M-row join.

This would drop execution time from 6s to probably < 200ms.

---

### Option B — Materialized View

```sql
CREATE MATERIALIZED VIEW module_totals_mv AS
SELECT
   m.id,
   m.carbon_report_id,
   m.module_type_id,
   m.status,
   max(e.updated_at) as updated_at,
   sum(em.kg_co2eq)/1000 as tco2_total
FROM ...
GROUP BY ...
```

Refresh:

```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY module_totals_mv;
```

Then query the MV.

---

# 🧠 Even Better Architecture

Your ERD shows:

- data_entries → data_entry_emissions
- carbon_report_modules → carbon_reports → units

You are calculating a **dashboard aggregation**.

Dashboards should NEVER compute raw transactional data live.

You need:

```
unit_year_aggregates table
```

Schema:

```
unit_id
year
validated_module_count
total_module_count
total_tco2
highest_module_type_id
last_update
```

Update it when:

- emission computed
- module validated
- report created

Then your query is a simple:

```sql
SELECT ...
FROM unit_year_aggregates
ORDER BY units.name
LIMIT 50
```

= < 20 ms.

---

# 🧪 Why You Spill to Disk

```
Batches: 64
temp read=66,635 written=66,635
```

Your `work_mem` is too small for the hash join.

You could try:

```sql
SET work_mem = '256MB';
```

But that only hides the symptom.

---

# 🥇 What I Would Do (If This Were My System)

1. Add missing indexes
2. Push `year` filter inside CTE
3. Remove materialized CTE
4. If still > 500ms → denormalize module total
5. For serious scale → precompute per unit/year table

---

# 📊 Your Cost Distribution

| Step                | Time        |
| ------------------- | ----------- |
| Seq Scan emissions  | 666 ms      |
| Hash Join emissions | 4.3 s       |
| HashAggregate       | 856 ms      |
| CTE Scan            | 6.1 s total |

Everything heavy happens before filtering.

---

# 🎯 Expected Gains

| Change                      | Expected Result |
| --------------------------- | --------------- |
| Add indexes                 | 30–50% faster   |
| Filter inside CTE           | 50–70% faster   |
| Denormalize totals          | 10x faster      |
| Precomputed dashboard table | 30–50x faster   |

---

If you want, I can:

- Rewrite the final optimized SQL version
- Design the denormalized schema
- Write the trigger
- Or help you benchmark variants properly

What level of aggressiveness do you want?

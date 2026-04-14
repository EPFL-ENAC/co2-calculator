This is already solid — let’s turn it into something a dev can **execute step-by-step without ambiguity**, and make a few key improvements (performance, correctness, extensibility).

---

# 📄 PRD 2 — Results CSV (`results.csv`)

## 🚀 0. Implementation Plan (READ FIRST)

Follow these steps **in order**:

### Step 1 — Ensure mapping table is correct

- Table: `emission_type_mapping`
- Must contain:
  - `id`, `name`
  - `category_id`, `subcategory_id`
  - `category_name`, `subcategory_name`

👉 If not populated, run:

```sql
UPDATE emission_type_mapping
SET
    category_id = (id / 10000) * 10000,
    subcategory_id = CASE
        WHEN id % 10000 >= 100 THEN (id / 100) * 100
        ELSE NULL
    END;
```

---

### Step 2 — Validate JSON structure

Ensure `carbon_reports.stats` contains:

```json
{
  "scope1": ...,
  "scope2": ...,
  "scope3": ...,
  "total": ...,
  "by_emission_type": {
    "10000": 123.4,
    "20000": 456.7
  }
}
```

👉 If `by_emission_type` is missing → STOP (data issue)

---

### Step 3 — Run base query (below)

👉 This generates the dataset

---

### Step 4 — Export

In pgAdmin:

- Run query
- Right-click → **Save as CSV**
- File name: `results.csv`

---

### Step 5 (optional, recommended)

Create a **materialized view** for performance:

```sql
CREATE MATERIALIZED VIEW carbon_report_results AS
<query below>;
```

---

# 🎯 1. Objective

Provide a dataset of **emissions per report × emission_type**, enriched with hierarchy:

- category
- subcategory
- emission type

Used for:

- analytics
- dashboards
- exports

---

# 📦 2. Scope

- One row per **(report_id × emission_type_id)**
- Source: `carbon_reports.stats`
- Enrichment: `emission_type_mapping`
- No recomputation from raw emissions

---

# 🧩 3. Data Sources

| Table                   | Role                        |
| ----------------------- | --------------------------- |
| `carbon_reports`        | aggregated emissions (JSON) |
| `emission_type_mapping` | hierarchy + labels          |

---

# 🧠 4. Data Model

### Granularity

```
1 row = 1 report × 1 emission_type
```

---

### Columns

| Column             | Type    | Description         |
| ------------------ | ------- | ------------------- |
| report_id          | integer | report identifier   |
| year               | integer | reporting year      |
| unit_id            | integer | unit identifier     |
| category_id        | integer | derived category    |
| subcategory_id     | integer | derived subcategory |
| category_name      | text    | category label      |
| subcategory_name   | text    | subcategory label   |
| emission_type_id   | integer | emission type       |
| emission_type_name | text    | emission label      |
| kg_co2eq           | float   | emissions           |

---

# 🧮 5. SQL Specification (FINAL)

## ✅ Recommended version (robust + explicit)

```sql
SELECT
    cr.id AS report_id,
    cr.year,
    cr.unit_id,

    etm.category_id,
    etm.subcategory_id,
    etm.category_name,
    etm.subcategory_name,

    etm.id AS emission_type_id,
    etm.name AS emission_type_name,

    (kv.value)::float AS kg_co2eq

FROM carbon_reports cr

-- 🔥 explode JSON (safer + faster than ? operator)
CROSS JOIN LATERAL jsonb_each(cr.stats->'by_emission_type') kv(key, value)

-- join mapping
JOIN emission_type_mapping etm
    ON etm.id = kv.key::int

ORDER BY
    cr.id,
    etm.category_id,
    etm.subcategory_id,
    etm.id;
```

---

## ⚠️ Why this version is better than original

| Change                      | Reason                      |
| --------------------------- | --------------------------- |
| `jsonb_each` instead of `?` | avoids repeated JSON lookup |
| `CROSS JOIN LATERAL`        | explicit row expansion      |
| direct join on `kv.key`     | faster + cleaner            |

---

# 📊 6. Output

- File: `results.csv`
- Format: CSV
- Sorted by:
  - report
  - category
  - subcategory
  - emission type

---

# ⚙️ 7. Constraints

| Constraint            | Behavior                     |
| --------------------- | ---------------------------- |
| Missing emission type | Not included                 |
| Missing mapping       | Row dropped (JOIN)           |
| JSON malformed        | Query fails                  |
| No aggregation        | Raw report-level values only |

---

# ⚡ 8. Performance Notes

- Query is **O(number of emission types × reports)**
- Typically fast (JSON already aggregated)
- Add index:

```sql
CREATE INDEX idx_carbon_reports_stats_gin
ON carbon_reports USING GIN (stats);
```

---

# 🔄 9. Optional Improvements

## Add scopes

```sql
(cr.stats->>'scope1')::float AS scope1,
(cr.stats->>'scope2')::float AS scope2,
(cr.stats->>'scope3')::float AS scope3,
(cr.stats->>'total')::float AS total,
```

---

## Add institutional_id

```sql
JOIN units u ON u.id = cr.unit_id
```

---

## Zero-fill missing emission types

👉 requires LEFT JOIN + full mapping scan (not current design)

---

## Materialized view (recommended)

```sql
CREATE MATERIALIZED VIEW carbon_report_results AS
SELECT ...
```

Refresh:

```sql
REFRESH MATERIALIZED VIEW carbon_report_results;
```

---

# 🧠 10. Design Decisions

| Decision          | Reason               |
| ----------------- | -------------------- |
| Use JSON stats    | already aggregated   |
| Use mapping table | decouples enum       |
| No pivot          | keeps flexibility    |
| LATERAL join      | proper JSON handling |
| No zero-fill      | smaller dataset      |

---

# 💬 TL;DR for the dev

1. Ensure `emission_type_mapping` is correct
2. Use `jsonb_each` to explode `stats.by_emission_type`
3. Join mapping
4. Export
5. (Optional) materialize

---

Example not completed (missing category/subcategory depends on what we want to display in the csv) (can import direct in DB)

"id" "name" "category_id" "subcategory_id" "category_name" "subcategory_name"
10000 "food" 10000 10000
10001 "food**vegetarian" 10000 10000
10002 "food**non_vegetarian" 10000 10000
20000 "waste" 20000 20000
20001 "waste**incineration" 20000 20000
20002 "waste**composting" 20000 20000
20003 "waste**biogas" 20000 20000
20004 "waste**recycling" 20000 20000
30000 "commuting" 30000 30000
30001 "commuting**walking" 30000 30000
30002 "commuting**cycling" 30000 30000
30003 "commuting**powered_two_wheeler" 30000 30000
30004 "commuting**public_transport" 30000 30000
30005 "commuting**car" 30000 30000
50000 "professional_travel" 50000 50000
50100 "professional_travel**train" 50000 50100
50101 "professional_travel**train**class_1" 50000 50100
50102 "professional_travel**train**class_2" 50000 50100
50200 "professional_travel**plane" 50000 50200
50201 "professional_travel**plane**first" 50000 50200
50202 "professional_travel**plane**business" 50000 50200
50203 "professional_travel**plane**eco" 50000 50200
60000 "buildings" 60000 60000
60100 "buildings**rooms" 60000 60100
60101 "buildings**rooms**lighting" 60000 60100
60102 "buildings**rooms**cooling" 60000 60100
60103 "buildings**rooms**ventilation" 60000 60100
60104 "buildings**rooms**heating_elec" 60000 60100
60105 "buildings**rooms**heating_thermal" 60000 60100
60200 "buildings**combustion" 60000 60200
60201 "buildings**combustion**natural_gas" 60000 60200
60202 "buildings**combustion**heating_oil" 60000 60200
60203 "buildings**combustion**biomethane" 60000 60200
60204 "buildings**combustion**pellets" 60000 60200
60205 "buildings**combustion**forest_chips" 60000 60200
60206 "buildings**combustion**wood_logs" 60000 60200
60300 "buildings**embodied_energy" 60000 60300
70000 "process_emissions" 70000 70000
70100 "process_emissions**ch4" 70000 70100
70200 "process_emissions**co2" 70000 70200
70300 "process_emissions**n2o" 70000 70300
70400 "process_emissions**refrigerants" 70000 70400
80000 "equipment" 80000 80000
80100 "equipment**scientific" 80000 80100
80200 "equipment**it" 80000 80200
80300 "equipment**other" 80000 80300
90000 "purchases" 90000 90000
90100 "purchases**goods_and_services" 90000 90100
90200 "purchases**scientific_equipment" 90000 90200
90300 "purchases**it_equipment" 90000 90300
90400 "purchases**consumable_accessories" 90000 90400
90500 "purchases**biological_chemical_gaseous" 90000 90500
90600 "purchases**services" 90000 90600
90700 "purchases**vehicles" 90000 90700
90800 "purchases**other" 90000 90800
90900 "purchases**additional" 90000 90900
90901 "purchases**additional**ln2" 90000 90900
100000 "research_facilities" 100000 100000
100100 "research_facilities**facilities" 100000 100100
100200 "research_facilities**animal" 100000 100200
110000 "external" 110000 110000
110100 "external**clouds" 110000 110100
110101 "external**clouds**virtualisation" 110000 110100
110102 "external**clouds**calcul" 110000 110100
110103 "external**clouds**stockage" 110000 110100
110200 "external**ai" 110000 110200
110201 "external**ai**provider_google" 110000 110200
110202 "external**ai**provider_mistral_ai" 110000 110200
110203 "external**ai**provider_anthropic" 110000 110200
110204 "external**ai**provider_openai" 110000 110200
110205 "external**ai**provider_cohere" 110000 110200
110206 "external**ai**provider_others" 110000 110200
2000301 "waste**biogas**organic_waste_food_leftovers" 2000000 2000300
2000302 "waste**biogas**cooking_vegetable_oil" 2000000 2000300
2000401 "waste**recycling**paper" 2000000 2000400
2000402 "waste**recycling**cardboard" 2000000 2000400
2000403 "waste**recycling**plastics" 2000000 2000400
2000404 "waste**recycling**glass" 2000000 2000400
2000405 "waste**recycling**ferrous_metals" 2000000 2000400
2000406 "waste**recycling**non_ferrous_metals" 2000000 2000400
2000407 "waste**recycling**electronics" 2000000 2000400
2000408 "waste**recycling**wood" 2000000 2000400
2000409 "waste**recycling**pet" 2000000 2000400
2000410 "waste**recycling**aluminum" 2000000 2000400
2000411 "waste**recycling**textile" 2000000 2000400
2000412 "waste**recycling**toner_and_ink_cartridges" 2000000 2000400
2000413 "waste**recycling**inert_waste" 2000000 2000400
6010101 "buildings**rooms**lighting**office" 6010000 6010100
6010102 "buildings**rooms**lighting**laboratories" 6010000 6010100
6010103 "buildings**rooms**lighting**archives" 6010000 6010100
6010104 "buildings**rooms**lighting**libraries" 6010000 6010100
6010105 "buildings**rooms**lighting**auditoriums" 6010000 6010100
6010106 "buildings**rooms**lighting**miscellaneous" 6010000 6010100
6010201 "buildings**rooms**cooling**office" 6010000 6010200
6010202 "buildings**rooms**cooling**laboratories" 6010000 6010200
6010203 "buildings**rooms**cooling**archives" 6010000 6010200
6010204 "buildings**rooms**cooling**libraries" 6010000 6010200
6010205 "buildings**rooms**cooling**auditoriums" 6010000 6010200
6010206 "buildings**rooms**cooling**miscellaneous" 6010000 6010200
6010301 "buildings**rooms**ventilation**office" 6010000 6010300
6010302 "buildings**rooms**ventilation**laboratories" 6010000 6010300
6010303 "buildings**rooms**ventilation**archives" 6010000 6010300
6010304 "buildings**rooms**ventilation**libraries" 6010000 6010300
6010305 "buildings**rooms**ventilation**auditoriums" 6010000 6010300
6010306 "buildings**rooms**ventilation**miscellaneous" 6010000 6010300
6010401 "buildings**rooms**heating_elec**office" 6010000 6010400
6010402 "buildings**rooms**heating_elec**laboratories" 6010000 6010400
6010403 "buildings**rooms**heating_elec**archives" 6010000 6010400
6010404 "buildings**rooms**heating_elec**libraries" 6010000 6010400
6010405 "buildings**rooms**heating_elec**auditoriums" 6010000 6010400
6010406 "buildings**rooms**heating_elec**miscellaneous" 6010000 6010400
6010501 "buildings**rooms**heating_thermal**office" 6010000 6010500
6010502 "buildings**rooms**heating_thermal**laboratories" 6010000 6010500
6010503 "buildings**rooms**heating_thermal**archives" 6010000 6010500
6010504 "buildings**rooms**heating_thermal**libraries" 6010000 6010500
6010505 "buildings**rooms**heating_thermal**auditoriums" 6010000 6010500
6010506 "buildings**rooms**heating_thermal**miscellaneous" 6010000 6010500

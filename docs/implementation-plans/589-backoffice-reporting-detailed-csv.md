# 📄 PRD 3 — Detailed CSVs (`*_data.csv`)

## 1. Objective

Provide **raw, traceable, and schema-specific data** for each data entry type.

This dataset is intended for:

- auditing
- debugging
- detailed analysis

---

## 2. Scope

- One CSV per `data_entry_type_id`
- One row per `data_entry`
- JSON data flattened into columns

---

## 3. Data Sources

- `data_entries`
- `data_entry_emissions`
- `carbon_report_modules`
- `carbon_reports`
- `units`

---

## 4. Data Model

### Granularity

- 1 row = 1 data_entry

---

## 5. Common Columns

| Column                | Description          |
| --------------------- | -------------------- |
| unit_institutional_id | unit identifier      |
| year                  | reporting year       |
| data_entry_id         | entry identifier     |
| kg_co2eq              | aggregated emissions |
| note                  | optional note        |

---

## 6. Key Rule

Each CSV:

- corresponds to one `data_entry_type_id`
- has its own schema
- flattens `data_entries.data` JSON

---

## 7. Base SQL Template

```sql
SELECT
    cr.year,
    u.institutional_id AS unit_institutional_id,
    de.id AS data_entry_id,
    de.data,
    SUM(dee.kg_co2eq) AS kg_co2eq

FROM data_entries de

JOIN carbon_report_modules crm
    ON crm.id = de.carbon_report_module_id

JOIN carbon_reports cr
    ON cr.id = crm.carbon_report_id

JOIN units u
    ON u.id = cr.unit_id

LEFT JOIN data_entry_emissions dee
    ON dee.data_entry_id = de.id

WHERE de.data_entry_type_id = <TYPE_ID>

GROUP BY
    cr.year,
    u.institutional_id,
    de.id,
    de.data;
```

---

## 8. Transformation

- Extract JSON fields using `->>` operator
- Cast values when needed
- Rename columns to match CSV contract

---

## 9. Example — Plane Travel

```sql
SELECT
    u.institutional_id,
    de.data->>'origin_iata' AS origin_iata,
    de.data->>'destination_iata' AS destination_iata,
    de.data->>'user_institutional_id' AS user_institutional_id,
    de.data->>'departure_date' AS departure_date,
    (de.data->>'number_of_trips')::int AS number_of_trips,
    de.data->>'cabin_class' AS cabin_class,
    de.data->>'note' AS note,

    SUM(dee.kg_co2eq) AS kg_co2eq

FROM data_entries de
JOIN carbon_report_modules crm ON crm.id = de.carbon_report_module_id
JOIN carbon_reports cr ON cr.id = crm.carbon_report_id
JOIN units u ON u.id = cr.unit_id
LEFT JOIN data_entry_emissions dee ON dee.data_entry_id = de.id

WHERE de.data_entry_type_id = 20

GROUP BY
    u.institutional_id,
    origin_iata,
    destination_iata,
    user_institutional_id,
    departure_date,
    number_of_trips,
    cabin_class,
    note;
```

---

## 10. Output

- Files: `<type_name>_data.csv`
- One file per `data_entry_type_id`

---

## 11. Constraints

- No mixing of types
- JSON schema must be stable per type
- Aggregation only at data_entry level

---

## 12. Future Improvements

- Automate SQL generation per type
- Add validation layer for schema consistency
- Build unified export pipeline (Python/dbt)

---

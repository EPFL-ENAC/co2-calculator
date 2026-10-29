---
status: delivered
issue: 3142
last_updated: 2026-10-29
summary: "Option 1: before the next train recalc, train trips at the 3 bus stops the rebuilt reference drops move to the nearest railway station. Hand-run SQL right after the reference upload, then a train recalc per affected year. No code change."
---

# 3142 — Move train trips off removed bus stops

## Problem

The rebuilt train reference (#939) keeps railway stations only. 8 prod
trip ends point at 3 bus stops it drops. The upload deletes every train
location and re-inserts the new ones, and it chains no recalc. The stored
emissions stay until the next train recalc, when `pre_compute` finds no
location and the trip silently computes to 0.

## Decision

Option 1. Each trip end moves to the nearest railway station in the new
reference. Its distance and emission change slightly.

| old key                                                | new station      | distance |
| ------------------------------------------------------ | ---------------- | -------- |
| `train:ch:ecublens vd epfl piccard:46.520373:6.568454` | Renens VD        | 2.0 km   |
| `train:ch:st-sulpice vd chantres:46.510484:6.553532`   | Denges-Echandens | 2.3 km   |
| `train:ch:zürich flughafen rega:47.458451:8.572914`    | Zürich Flughafen | 1.2 km   |

Renens VD and Denges-Echandens have the same key in the old and new
reference. Zürich Flughafen exists only in the new one, so the move runs
after the upload.

A trip whose other end is already the new station would become 0 km. The
move refuses to apply then, and that trip falls back to option 2 (the
owner re-enters it as a bus trip).

## Runbook, per environment

A human runs every query; agents never touch a shared database.

1. **Dry-run** (any time, before the upload). Post the output on #3142: it
   is the before snapshot and the audit trail. The SQL bypasses
   `audit_documents`.
   Every row must have `collapses = false`. Each year in the output needs a
   recalc in step 5.
2. **Upload** `travel_trains_reference.csv` in the backoffice.
3. **Apply**, straight after the upload. Any train recalc between steps 2
   and 3 zeroes the moved trips. It raises and rolls back if a target
   station is missing or ambiguous, or if a trip collapses.
4. **Gate**: the orphan query must return no rows. On dev and stage it may
   list keys the prod mapping does not cover. Stop and decide those first.
5. **Recalc** train for every year from step 1. The backoffice has no
   button for it since #780, and "Recompute stats" only re-sums stored
   emissions. Logged in as superadmin, run in the browser console:
   `await (await fetch('/api/v1/sync/recalculate-emissions/2/21?year=<year>', { method: 'POST', credentials: 'include' })).json()`
   (professional travel = 2, train = 21). Then run the after query on the
   dry-run ids and post before/after on #3142.

Order across environments: dev, then stage, then prod. Where the new
reference is already uploaded, skip step 2.

### 1. Dry-run

`module_status`: 0 not started, 1 in progress, 2 validated. Before the
upload `new_key` is NULL for Zürich Flughafen, which is harmless: no trip
can use a key the old reference lacks. After the upload every moved end
must show a `*_new_key`; a NULL means the name did not resolve.

Copy the SQL from the file, never from a wrapped terminal: a wrapped line
pastes a newline into a string literal, and the name stops matching.

```sql
WITH move AS (
  SELECT m.old_key, m.new_name, l.natural_key AS new_key
  FROM (VALUES
    ('train:ch:ecublens vd epfl piccard:46.520373:6.568454', 'Renens VD'),
    ('train:ch:st-sulpice vd chantres:46.510484:6.553532',   'Denges-Echandens'),
    ('train:ch:zürich flughafen rega:47.458451:8.572914',    'Zürich Flughafen')
  ) AS m(old_key, new_name)
  LEFT JOIN locations l
    ON l.transport_mode = 'train' AND l.country_code = 'CH' AND l.name = m.new_name
)
SELECT de.id, cr.year, crm.status AS module_status, de.status AS entry_status,
       de.data->>'origin_natural_key' AS origin_key,
       de.data->>'origin_name' AS origin_before,
       coalesce(mo.new_name, de.data->>'origin_name') AS origin_after,
       de.data->>'destination_natural_key' AS destination_key,
       de.data->>'destination_name' AS destination_before,
       coalesce(md.new_name, de.data->>'destination_name') AS destination_after,
       mo.new_key AS origin_new_key, md.new_key AS destination_new_key,
       coalesce(mo.new_key, de.data->>'origin_natural_key')
         = coalesce(md.new_key, de.data->>'destination_natural_key') AS collapses,
       (SELECT sum(e.kg_co2eq) FROM data_entry_emissions e
         WHERE e.data_entry_id = de.id) AS kg_before
FROM data_entries de
JOIN carbon_report_modules crm ON crm.id = de.carbon_report_module_id
JOIN carbon_reports cr ON cr.id = crm.carbon_report_id
LEFT JOIN move mo ON mo.old_key = de.data->>'origin_natural_key'
LEFT JOIN move md ON md.old_key = de.data->>'destination_natural_key'
WHERE de.data_entry_type_id = 21
  AND (mo.old_key IS NOT NULL OR md.old_key IS NOT NULL)
ORDER BY de.id;
```

### 3. Apply

```sql
BEGIN;

-- Targets resolve from the uploaded reference, not hand-typed keys.
CREATE TEMP TABLE station_move ON COMMIT DROP AS
SELECT m.old_key, m.new_name, l.natural_key AS new_key
FROM (VALUES
  ('train:ch:ecublens vd epfl piccard:46.520373:6.568454',
   'Renens VD'),
  ('train:ch:st-sulpice vd chantres:46.510484:6.553532',
   'Denges-Echandens'),
  ('train:ch:zürich flughafen rega:47.458451:8.572914',
   'Zürich Flughafen')
) AS m(old_key, new_name)
LEFT JOIN locations l
  ON l.transport_mode = 'train'
 AND l.country_code = 'CH'
 AND l.name = m.new_name;

DO $$
BEGIN
  IF (SELECT count(*) <> 3 OR count(new_key) <> 3
      FROM station_move) THEN
    RAISE EXCEPTION 'a target is not exactly one train location';
  END IF;
END $$;

UPDATE data_entries de
SET data = (de.data::jsonb
  || coalesce((
       SELECT jsonb_build_object(
                'origin_natural_key', m.new_key,
                'origin_name', m.new_name)
       FROM station_move m
       WHERE m.old_key = de.data->>'origin_natural_key'
     ), '{}'::jsonb)
  || coalesce((
       SELECT jsonb_build_object(
                'destination_natural_key', m.new_key,
                'destination_name', m.new_name)
       FROM station_move m
       WHERE m.old_key = de.data->>'destination_natural_key'
     ), '{}'::jsonb)
)::json
WHERE de.data_entry_type_id = 21
  AND (de.data->>'origin_natural_key'
         IN (SELECT old_key FROM station_move)
       OR de.data->>'destination_natural_key'
         IN (SELECT old_key FROM station_move));

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM data_entries
    WHERE data_entry_type_id = 21
      AND data->>'origin_natural_key'
            IN (SELECT new_key FROM station_move)
      AND data->>'origin_natural_key'
            = data->>'destination_natural_key'
  ) THEN
    RAISE EXCEPTION 'a moved trip starts and ends at one station';
  END IF;
END $$;

COMMIT;
```

`psql` prints `UPDATE n`; `n` must equal the dry-run row count.

### 4. Gate

```sql
SELECT k.natural_key, count(*) AS trips
FROM data_entries de
CROSS JOIN LATERAL (VALUES (de.data->>'origin_natural_key'),
                           (de.data->>'destination_natural_key')) AS k(natural_key)
LEFT JOIN locations l ON l.natural_key = k.natural_key
WHERE de.data_entry_type_id = 21 AND k.natural_key IS NOT NULL
  AND l.natural_key IS NULL
GROUP BY 1
ORDER BY trips DESC;
```

### 5. After

```sql
SELECT data_entry_id, sum(kg_co2eq) AS kg_after
FROM data_entry_emissions
WHERE data_entry_id IN (/* ids from the dry-run */)
GROUP BY 1
ORDER BY 1;
```

## Prod, 2026-10-29

The reference was uploaded before the dry-run; no recalc ran in between,
so `kg_before` held. 8 entries moved, all in 2025, none collapsed. The
first apply hit the target guard: the SQL had been copied from a wrapped
terminal. It rolled back cleanly and the re-run from a file committed.

Distance rounds to whole km (`calculate_train_distance`), so a 2 km shift
leaves some trips unchanged.

| ids            | trip                    | kg before | kg after |
| -------------- | ----------------------- | --------- | -------- |
| 309156, 309157 | Sion ↔ Renens VD        | 22.75196  | 22.75196 |
| 309410, 309411 | Genève ↔ Renens VD      | 5.4824    | 5.7761   |
| 309760, 309761 | Bern Hbf ↔ Denges-Ech.  | 2.937     | 2.937    |
| 309764, 309765 | Nyon ↔ Zürich Flughafen | 2.51603   | 2.50624  |

Total over the 8 entries: 67.37 → 67.94 kg CO₂-eq.

Dev and stage: when their train reference is uploaded, run the gate
query first, then this runbook if it lists anything.

## Out of scope

- An upload guard that refuses to drop a key a trip still uses. It would
  block this very upload; file it as its own issue if wanted.
- `pre_compute` logging and returning `{}` on a missing key is the silent
  fallback behind this issue. Same follow-up.

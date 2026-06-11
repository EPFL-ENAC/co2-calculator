# Backend Seed Data

This page is the orientation guide for the seed scripts that bootstrap
a local backend with realistic data. It covers what each `make` target
produces, when to use which, and how the seeded scopes line up with
login-test so a developer can reach a perimeter and see real numbers.

For broader backend context see:

- [Overview](01-overview.md) - High-level architecture
- [Permission System](06-PERMISSION-SYSTEM.md) - Role/scope model
- [Integration Testing](10-INTEGRATION-TESTING.md) - Test-time fixtures

## The two seeders

The repo ships two distinct seed pipelines:

| Target                  | Volume                  | Source                       | Use when                                                                                                                                                  |
| ----------------------- | ----------------------- | ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `make seed-data`        | Small, deterministic    | CSVs in `backend/seed_data/` | You need predictable reference data (factors, locations, building rooms, generic data entries). Default for local dev and CI fixtures.                    |
| `make seed-data-random` | ~800k `data_entry` rows | Faker + the same factor CSVs | You need scale: perf testing, pagination work, query-plan checks, populated charts. Issue [#222](https://github.com/EPFL-ENAC/co2-calculator/issues/222). |

`seed-data-random` chains the random unit/user/year/project/report generators
with the canonical CSV-driven factor seeder, so factor classes stay aligned
with the generated equipment `(class, sub_class)` payloads.

## What `seed-data-random` produces

Run order (see `backend/app/seed/random_generator/seed_all.py`):

1. **500 units + 4000 users + 2 admins** — units have `institutional_code`
   `U00000`-`U00499` and `institutional_id` `CF00000`-`CF00499`.
2. **3 year_configuration rows** — 2023/2024/2025, provider DEFAULT,
   `is_started=TRUE`, `configuration_completed=now()`. Without these
   the UI gates the year picker.
3. **500 carbon_projects + 1500 carbon_reports + carbon_report_modules** —
   one Calculator project per unit, one report per (project, year), all
   8 module types per report.
4. **Factors from `backend/seed_data/*_factors.csv`** — canonical reference
   set; equipment classes are then used to seed `data_entry` payloads.
5. **~800k data_entries + matching emissions** — sized via
   `NUM_UNITS × YEARS × ALL_MODULE_TYPE_IDS × ENTRIES_PER_MODULE`.

## Login-test perimeter map

Seeded users carry roles whose scope binds to a unit's `institutional_id`
(the cf-style key, `CF00000`+):

| User pattern            | Role                               | Scope                                    |
| ----------------------- | ---------------------------------- | ---------------------------------------- |
| `USR000000`-`USR003999` | CO2_USER_STD or CO2_USER_PRINCIPAL | Single unit (`institutional_id=CF…`)     |
| `ADMIN004000`           | CO2_BACKOFFICE_METIER              | An affiliation (`SB`, `STI`, `IC`, `SV`) |
| `ADMIN004001`           | CO2_SUPERADMIN                     | Global                                   |

In login-test, picking any `USR…` user lands you on that user's unit
perimeter. Picking the SUPERADMIN puts you in global scope; picking the
METIER admin scopes you to the affiliation row visible in the role.

## When the seed fails

The seed assumes a clean DB. If a step mid-pipeline fails and you retry,
previously-committed rows collide on unique constraints (e.g.
`ix_units_institutional_code`). Recover with:

```bash
make db-drop && make db-create && make db-migrate && make seed-data-random
```

## Tuning the volume

`seed-data-random` volume is driven by four constants:

- `NUM_UNITS`, `NUM_USERS` in
  `backend/app/seed/random_generator/populate_units_and_users.py`
- `ENTRIES_PER_MODULE_MIN`, `ENTRIES_PER_MODULE_MAX` in
  `backend/app/seed/random_generator/seed_data_entries.py`

Expected total rows = `NUM_UNITS × YEARS (3) × ALL_MODULE_TYPE_IDS (8) ×
avg(ENTRIES_PER_MODULE)`. The smoke test
`tests/unit/seed/test_random_generator_builders.py::test_entries_per_module_window_targets_800k_rows`
fails CI if a change moves the math outside the 700k-900k band — bump it
in the same PR if you really mean to retarget.

## See also

- Implementation plan: [222-seed-data-faker.md](../implementation-plans/222-seed-data-faker.md)
- Factor CSV formats: [`backend/05-seed-data` subsection](csv-seed-formats/)
- ADR-018: [Factor CSV delete-before-insert](../architecture-decision-records/018-factor-csv-delete-before-insert.md)

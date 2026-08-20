# backend/scripts

One-off and maintenance scripts. All are plain Python entry points — run
them through `uv run` from `backend/` so they see the app's installed
packages and settings (`app.core.config`, `.env`, etc.):

```bash
cd backend
uv run python -m scripts.<name> [args]
```

## generate_perf_test_csvs.py

Generates ceiling-scale CSVs for manual performance testing (#2161): one
file per `DataEntryTypeEnum`, sized at the real per-unit-year ceilings from
issue #2161. Rows are sampled from the real reference/factor files in
`backend/INPUT_DATA/` (gitignored, developer-supplied — same precondition as
`make bootstrap-years`) rather than invented, so every row resolves to a
real factor instead of exercising the ingest error path.

```bash
uv run python -m scripts.generate_perf_test_csvs                 # all types
uv run python -m scripts.generate_perf_test_csvs --only plane
uv run python -m scripts.generate_perf_test_csvs --out /tmp/perf --scale 2
```

Output goes to `backend/INPUT_DATA/perf/` by default (gitignored, nothing
committed). Upload each CSV via the module-unit-specific ingest path with
`data_entry_type_id` set explicitly to the target type — the CSV itself
carries no type/category column. There is no CSV for Simulator Plan (no
ingest path) or for `building_construction_renovation` (derived
server-side from `building` rows) — see the script's own docstring.

## build_train_seed_from_trainline.py

One-time seed builder (#1183): converts the trainline-eu `stations.csv`
dump (gitignored, `backend/stations.csv`) into
`backend/seed_data/seed_travel_location_train.csv`, the schema the
reference-data CSV ingestion expects. Re-run only when refreshing the
station dataset from upstream.

```bash
uv run python -m scripts.build_train_seed_from_trainline
```

## dedupe_member_roles.py

Reports — and optionally cleans — duplicate member roles that violate
`uq_member_role_per_module` (#2050 J4). Run against an environment **before**
deploying the migration that creates that index; the migration refuses to
run while duplicates exist. Only deletes rows whose payload is byte-identical
to the one it keeps — a group that differs (different FTE, different name)
is reported and left for a maintainer to resolve.

```bash
uv run python -m scripts.dedupe_member_roles              # report only
uv run python -m scripts.dedupe_member_roles --fix        # delete safe dupes
uv run python -m scripts.dedupe_member_roles --fix --yes  # no confirmation
```

## audit_test_users.py / migrate_test_users.py

Paired one-time scripts from the authentication-hardening work: `audit_*`
checks for TEST-provider users whose `institutional_id` lacks the `TEST-`
prefix (exit code non-zero if any are found); `migrate_*` fixes them.
Run the audit first, and run the migration **before** deploying the
auth-hardening change it supports.

```bash
uv run python -m scripts.audit_test_users
uv run python -m scripts.migrate_test_users
```

## manage_db.py

Drops or creates a Postgres database via the superuser connection derived
from `DB_URL`. Used by local/CI setup, not normal development.

```bash
uv run python -m scripts.manage_db --action create [--db-name NAME]
uv run python -m scripts.manage_db --action drop [--db-name NAME]
```

---
status: delivered
issue: 2161
last_updated: 2026-08-20
summary: "Extend backend/scripts/generate_perf_test_csvs.py from 3 coarse
  categories (travel/buildings/purchase) to one generator per
  DataEntryTypeEnum, sized at #2161's real per-type ceilings, plus a
  scripts/README.md covering every script in the folder."
---

# Manual perf-test CSV generator: one file per data_entry_type (#2161)

Backfilled — delivered directly, no plan-first pass (small, mechanical
extension of an existing script with an explicit ceiling table given).

## What changed

`backend/scripts/generate_perf_test_csvs.py` previously generated 3 coarse
CSVs (`travel`, `buildings`, `purchase`) whose row counts were the _sum_ of
several `DataEntryTypeEnum` ceilings, hiding which type the rows actually
targeted and mixing e.g. all 7 purchase categories into one arbitrary file.
It now has one generator per calculator `DataEntryTypeEnum` (23 types),
sized at #2161's real per-unit-year ceilings (same numbers documented in
`2161-ceiling-scale-perf-fixtures.md`'s `CEILING_PER_UNIT_YEAR` table).

Each generator samples real rows from `backend/INPUT_DATA/*_factors.csv` /
`*_reference.csv` (gitignored, developer-supplied) so every emitted row
resolves to a real factor — an unresolvable value fails the row since #2050
Track J1, so inventing values would measure the error path, not the module.
Where a type shares its factor table with siblings (equipment's
`scientific`/`it`/`other`, purchase's 7 categories), one parametrized
generator filters the shared table by category rather than duplicating
near-identical code per type.

`building_construction_renovation` (data_entry_type 32, still named
`building_embodied_energy` in the model) has no CSV ingest — it's derived
server-side from `building` rows during ingest. The generator table
documents this and returns no file rather than fabricating one.

## Why not `app/seed/ceilings.py`

`2161-ceiling-scale-perf-fixtures.md` plans a `CEILING_PER_UNIT_YEAR` dict
in `app/seed/ceilings.py` as the single source of truth for these numbers,
but that module doesn't exist yet on this branch (it's Task 1 of that
plan, not merged). This script hardcodes the same numbers directly, mirroring
its own prior style (a module-level `CEILINGS` dict) rather than depending
on unmerged code. When `app/seed/ceilings.py` lands, re-key this script's
`CEILINGS` off `CEILING_PER_UNIT_YEAR` to keep the two from drifting.

## Also added

`backend/scripts/README.md` — a one-page index of every script in the
folder (this generator plus the pre-existing audit/migrate/dedupe/seed/db
scripts), each with its purpose and invocation, since none existed before.

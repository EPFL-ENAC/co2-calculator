---
status: in-progress
issue: 259
last_updated: 2026-08-18
title: "Equipment: carry forward prior-year usage with factor/default fallback"
summary: "At bulk ingest, usage hours set in the unit's most recent prior year are carried onto the matching equipment_id (per field, one lookup query per unit/year); a field the prior year left unset keeps tracking the factor suggestion, and when the factor has none either the emission formula falls back to the spec defaults (active 12h, standby 156h per week). No schema or frontend change."
---

# Equipment: carry forward prior-year usage with factor/default fallback

Branch `fix/259-equipment-identify-data-entry-different-from-previous-years`,
round 3 of issue **#259**.

## Context

Round 1 (merged to `dev`, `0706df6fb`) covered the "identify" half of the
issue: equipment whose `equipment_id` is absent from the unit's most recent
prior year is flagged new, sorted first, and counted in the module banner
(`get_prior_year_equipment_ids`, the new-and-incomplete primary sort,
`count_incomplete_new_equipment`).

The updated issue spec added the data-entry half: usage hours the unit
already confirmed in a previous campaign should not have to be re-typed
every year, and equipment with no usage information anywhere should still
compute an emission from sensible defaults instead of computing nothing.

Round 2 (kept on `backup/259-carry-forward-v1`, `63bd7847f`) resolved the
carry-forward at read time and surfaced provenance through derived response
flags and widened response types. It was dropped: no new response fields, no
type widening — the design must stay schema-free.

## Decision

Per-field resolution chain for `active_usage_hours_per_week` and
`standby_usage_hours_per_week`, applied independently to each field:

1. **Value ingested this year** — normally absent (the feed does not carry
   usage), but if present it is still overridden by rule 2, since a value
   the user confirmed in a prior campaign is more trustworthy than a feed
   artifact.
2. **Value set in the unit's most recent prior year** for the same
   `equipment_id` — copied into `entry.data` at bulk ingest.
3. **Factor suggestion** — an unset field keeps tracking the factor's
   current `active/standby_usage_hours_per_week` live in the emission
   formula (nothing seeded into `entry.data`, so a factor re-upload takes
   effect on recompute).
4. **Spec defaults** — when the factor has none either, the formula falls
   back to `DEFAULT_ACTIVE_USAGE_HOURS_PER_WEEK = 12` /
   `DEFAULT_STANDBY_USAGE_HOURS_PER_WEEK = 156` (12 + 156 = a full 168 h
   week). The formula no longer returns `None` for missing hours.

Consequences of the chain:

- **No response-schema or frontend change.** A carried-forward value is an
  ordinary `entry.data` value; an unconfirmed cell still surfaces through
  the existing empty-cell UX and the round-1 incomplete count. This is what
  keeps round 3 schema-free where round 2 was not.
- **"Prior year" is the greatest year strictly before the current one that
  has equipment entries for the unit** — robust to skipped campaign years,
  same definition round 1 used for the new flag (shared
  `_prior_equipment_year` helper).
- **Carry-forward happens once, at write time.** Editing the value later
  behaves like any other edit; prior years are never re-read after ingest.

## Backend

- `app/modules/equipment/data_entries.py` — the two spec-default constants.
- `app/modules/equipment/handlers.py` — `_equipment_formula` gains the
  default fallback per field; the `return None` on missing hours is gone.
- `app/repositories/data_entry_repo.py`
  - `_prior_equipment_year(unit_id, current_year)` — factored out of
    `get_prior_year_equipment_ids` (round 1) so both lookups share the
    prior-year definition.
  - `get_prior_year_equipment_usage(unit_id, current_year)` — maps
    `equipment_id` → the usage fields **actually set** in the prior year.
    Single query per (unit, year); only `equipment_id` and the two usage
    fields travel over the wire, so a 50k-row prior year stays cheap.
    Unset fields are omitted from each dict, so the caller can merge
    without inventing values the prior year never had.
- `app/services/data_entry_service.py` —
  `apply_equipment_carry_forward(data_entries)`, called from the bulk-copy
  ingest path after `fill_denormalized_scope`. Filters to equipment entries
  with an `equipment_id`, resolves each entry's (unit, year) scope, and
  merges the prior-year map over `entry.data`. Prior-year maps are cached
  per `(unit_id, year)` on the service instance: one lookup query per
  unit/year in a batch, never one per entry.

## Tests

- `tests/integration/.../test_new_vs_previous_year.py`
  - `test_prior_year_usage_map_partial_fields` — the lookup returns only
    the fields each prior row set; the prior year itself gets an empty map.
  - `test_apply_equipment_carry_forward` — per-field merge: prior-year
    values win over ingested ones, unset prior fields stay as ingested,
    unmatched equipment is untouched; entries arrive unstamped like the
    real ingest batch (denormalized scope filled by the service).
  - `test_new_equipment_flagged_and_sorted_first` repaired: the primary
    sort floats **new-and-incomplete** rows, so the new row is now seeded
    without usage — the complete row it previously seeded could never
    float and the assertion had been failing since the round-1 commit.
- `tests/unit/modules/test_equipment_schemas.py` —
  `test_equipment_formula_spec_defaults_when_no_hours_anywhere` replaces
  the old none-when-no-hours test: with no hours on the entry nor the
  factor the 12/156 defaults apply, each field independently (5 h active on
  the entry still combines with the 156 h standby default).

## Delivery

- Branch `fix/259-equipment-identify-data-entry-different-from-previous-years`,
  commit `1ddaf8a3e` on top of round 1; round 2 preserved on
  `backup/259-carry-forward-v1`.

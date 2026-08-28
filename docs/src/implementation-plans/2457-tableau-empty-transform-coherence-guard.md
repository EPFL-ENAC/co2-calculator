---
status: delivered
issue: 2457
last_updated: 2026-08-28
title: "Tableau empty-transform: prove coherence before treating as routine"
summary: "_finalize_empty_transform decided routine (delete-and-replace) vs. genuine error (raise, delete nothing) purely from the *names* of fired drop reasons, never the values behind them. A casing or date-format drift upstream could tag every row under an 'expected' reason and silently wipe a year's data. Adds a per-provider coherence check that must also hold before trusting the routine path."
---

# Tableau empty-transform: prove coherence before treating as routine (#2457)

## Problem

`_finalize_empty_transform` (`base_tableau_api_provider.py`) decided whether
an all-rows-dropped Tableau sync was routine (delete-and-replace) or a
genuine error (raise, delete nothing) by checking whether the _names_ of
fired drop reasons were a subset of `EXPECTED_EMPTY_DROP_REASONS` — never
whether the underlying values made sense.

For `ResearchFacilitiesApiProvider`,
`EXPECTED_EMPTY_DROP_REASONS = {"client_type", "year"}`, checked via plain
string compares (`client_type != "INTERNE"`, `date_iso[:4] != year`). If the
upstream Tableau datasource changed casing (`"Interne"`) or date format,
every row would be dropped under one of these "expected" reasons and
`_delete_existing_api_entries()` would wipe the year's data — a silent
full-year data loss logged as `WARNING`, not an error.

The docstring on `_delete_existing_api_entries` ("called only after at least
one valid replacement row has survived") was also false, since
`_finalize_empty_transform` called it with zero surviving rows whenever
`expected` was true.

## What shipped

- `base_tableau_api_provider.py` — extracted the name-based subset check
  into an overridable hook, `_empty_transform_is_routine(raw_data)`.
  `_finalize_empty_transform` now takes the raw fetched rows (not just a
  count) and defers to this hook. Default behavior (name-subset only) is
  unchanged for providers that don't override it — currently
  `ProfessionalTravelApiProvider` and `HeadcountMembersApiProvider`, whose
  `EXPECTED_EMPTY_DROP_REASONS` is empty, so the routine branch was already
  dead code for them and stays so.
- `research_facilities_api_provider.py` — overrides the hook to also prove
  the datasource still looks structurally coherent before trusting "no
  INTERNE rows this year":
  - at least one raw row anywhere in the fetch (not just kept rows) has
    `client_type == "INTERNE"` exactly — proves the field/value/casing
    still matches;
  - every one of those internal rows has a plausible 4-digit year prefix
    (1900–2100) on `date_iso` — proves the date format hasn't drifted
    (guards against e.g. epoch-millis or `DD/MM/YYYY` still slicing to 4
    digits).

  Both must hold, or the empty transform raises instead of wiping the year.
  (`# ponytail:` marks the "at least one" check as an existence proof only —
  a mixed-casing datasource would still pass; tighten to a ratio if that
  ever shows up in practice.)

- `_delete_existing_api_entries`'s docstring now documents the zero-rows
  exception explicitly (a routine empty transform still calls it) instead
  of stating an invariant the code no longer holds.
- Two regression tests in
  `test_research_facilities_drop_reasons.py`
  (`test_client_type_casing_drift_raises_instead_of_wiping_data`,
  `test_date_format_drift_raises_instead_of_wiping_data`) — synthetic
  fetches where casing/date-format drift would previously have silently
  wiped the year; confirmed to fail without the fix (verified by
  temporarily reverting the override to the base's name-only check) and
  pass with it, including asserting `_delete_existing_api_entries` is never
  called. Existing tests updated only for the `_finalize_empty_transform`
  signature change (count → raw rows); no behavior assertions changed.

## Scope note

`EXPECTED_EMPTY_DROP_REASONS` is non-empty only for
`ResearchFacilitiesApiProvider`, so the coherence gap was live only there.
No broader Tableau-provider decision was needed.

## Verification

- `uv run pytest tests/unit/services/data_ingestion/` — 300 passed.
- `uv run ruff check` / `uv run ruff format --check` on touched files — clean.
- `uv run ty check` — clean.

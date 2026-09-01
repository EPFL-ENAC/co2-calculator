---
status: delivered
issue: "996"
last_updated: 2026-09-01
summary: BaseCSVProvider._process_row hardcodes the factor tuple slot to None; dropping the unreliable rows_with_factors/rows_without_factors counter (Option C) rather than inventing a signal that doesn't exist yet.
---

# 996 — `_process_row` factor counter always reports `rows_without_factors`

## Root cause (confirmed)

- `_process_row` (`backend/app/services/data_ingestion/base_csv_provider.py:1357`)
  always does `return data_entry, None, None, kg_co2eq_override` — position 3
  (`factor`) is a literal `None`, never the result of anything.
- The caller, `process_csv_in_batches` (`base_csv_provider.py:1055-1058`), does
  `if factor: stats["rows_with_factors"] += 1 else:
stats["rows_without_factors"] += 1` — so every successfully processed row
  lands in `rows_without_factors`.
- Confirmed to pre-date #988: parent commit `b39fec7e` already had
  `return data_entry, None, None`. #988 only appended the 4th element
  (`kg_co2eq_override`). Matches the issue's origin note and
  `docs/code-review/988-copilot-feedback-fix-data-entry-stop-persisting-computed-fields-to-dataentry-data.md`,
  "Skipped after verification" section.

## Premise gap found during investigation

The issue's suggested fix assumes "the resolution logic is already in
`_process_row`" and this is pure return-value plumbing. True for exactly one
of four ingestion paths, false for the rest:

- **MODULE_PER_YEAR, priority-3 type inference**
  (`csv_providers/module_per_year.py:167-216`): when `data_entry_type_id`
  isn't given by job config or a CSV category column, it infers the type via
  `lookup_data_entry_type_by_kind`, which scans `factors_map`. A hit here
  _is_ a genuine "this row's kind/subkind matched a factor" signal — but it's
  discarded; only the resulting `DataEntryTypeEnum` survives.
- **MODULE_PER_YEAR, priority 1/2** and **all of MODULE_UNIT_SPECIFIC**
  (`csv_providers/module_unit_specific.py:55-99`): `data_entry_type` comes
  straight from job config or a category column. No `factors_map` lookup
  ever runs. Both subclasses' docstrings claim _"factor validation is
  handled by ModuleHandlerService when it queries the database in
  `_process_row`"_ — checked, and it doesn't hold:
  - `ModuleHandlerService` (`app/services/module_handler_service.py`) only
    has taxonomy-tree and typeahead methods for the UI; no per-row match
    check.
  - `require_factor_to_match` (`app/schemas/data_entry.py:136,279`) is read
    exactly once in the whole backend — at setup time in
    `_guard_factors_required` (fail-fast when `factors_map` is empty for a
    module that needs it) — never per row.
  - `validate_create` is a synchronous pydantic call with no DB session, so
    it isn't doing a live factor lookup either.
  - **Conclusion: for most rows, "does this row have a matching factor" is
    not computed anywhere in the ingestion path today.** The docstring is
    stale/aspirational, not a pointer to real code.

## Related, out of scope for this issue

- `api_providers/base_tableau_api_provider.py` declares the identical
  `rows_with_factors`/`rows_without_factors` pair (lines 46-47, 853-854) and
  never increments either — professional-travel API ingestion always
  reports 0/0 for both. Same flavor of bug, different class hierarchy
  (`DataIngestionProvider`, not `BaseCSVProvider`). Not touched here; flag as
  a possible follow-up issue.
- `frontend/src/stores/backofficeDataManagement.ts:67-68` types the two
  fields but nothing renders them structurally — they only reach the user
  pre-formatted inside the backend's summary sentence
  (`base_csv_provider.py:1440-1441`). No frontend behavior change either way.

## Options

**A — Make the counter real for the one path that already checks.** Return
whether `lookup_data_entry_type_by_kind` matched, for MODULE_PER_YEAR
priority-3 rows only. Priority-1/2 and MODULE_UNIT_SPECIFIC rows still need a
default (e.g. always counted as "with factor," since no check applies to
them) — closer to correct than today, but the semantics differ by entity
type and the default is itself a judgment call.

**B — Extend the check to every row.** Add a `factors_map` existence check to
the priority-1/2 path too, reusing the kind/subkind key logic that today only
lives inside `seed_helper.lookup_data_entry_type_by_kind`. Makes the stat
uniform and honest, but is new logic on a path that currently has none — a
design change, not plumbing.

**C — Drop the counter (recommended).** Delete
`rows_with_factors`/`rows_without_factors` from `StatsDict`, its
initialization, the increment, and the summary sentence
(`base_csv_provider.py:110-111,898-899,1055-1058,1440-1441`); update the 4
backend tests that reference the keys; drop the two optional fields from the
frontend type. A number nobody can currently compute correctly is worse than
no number ("no silent fallbacks"). Smallest diff; matches the issue's own
stated impact ("user-visible only via job summary text").

## Decision

**Option C**, confirmed by Guilbert 2026-09-01. Smallest, most honest diff,
and nothing structurally depends on the counter downstream. A and B both
require deciding what "has a factor" means for entity types that never check
today — a real design conversation, not a bug fix — parked, not pursued here.

## Regression test

Assert the job summary/status message no longer mentions factor counts and
`StatsDict` no longer carries `rows_with_factors`/`rows_without_factors`;
assert `process_csv_in_batches` still completes end-to-end (no `KeyError`
from the removed keys, no leftover reference in the summary string).

## Implementation checklist

- [x] `base_csv_provider.py`: removed `rows_with_factors`/`rows_without_factors`
      from `StatsDict`, init, the `if factor: ... else: ...` increment (kept
      `stats["rows_processed"] += 1`), and the summary sentence fragments.
- [x] `_process_row` return type: dropped the always-`None` 3rd tuple element
      (`factor`) — signature, docstring, every `return` statement, and the
      caller's unpack all updated to a 3-tuple
      `(DataEntry | None, str | None, kg_co2eq_override)`.
- [x] Found and fixed a ripple the checklist hadn't accounted for:
      `csv_providers/local_seed.py` overrides `_process_row` (forwards to
      `super()`) and had its own now-stale 4-tuple return annotation — updated
      to match.
- [ ] ~~`_resolve_handler_and_validate`: drop the dead `factor: Any | None`
      parameter~~ — descoped. That parameter is independent of `_process_row`'s
      return tuple (it's an input, always `None`, ignored by both subclass
      overrides) and touching it would have rippled into 11 more test call
      sites across `test_module_per_year_csv_provider.py` and
      `test_module_unit_specific_csv_provider.py` for zero behavior change.
      Left as a separate, still-dead cleanup opportunity — not part of the
      scope Guilbert approved for this issue.
- [x] Updated the backend tests referencing the two keys:
      `test_base_csv_provider.py` (`_build_stats`/`_make_stats` helpers, the
      `test_stats_dict_structure` assertions, the `_finalize_and_commit`
      summary-message assertion, and 10 `_process_row` call sites unpacking
      the old 4-tuple), `test_module_per_year_csv_provider.py`, and
      `test_module_unit_specific_csv_provider.py`.
      `test_professional_travel_api_provider.py` confirmed out of scope
      (exercises `BaseTableauApiProvider`'s separate `StatsDict`, untouched)
      and left alone.
- [x] `frontend/src/stores/backofficeDataManagement.ts:67-68`: dropped the two
      optional fields — grep confirmed nothing else in `frontend/src`
      referenced them.
- [x] Regression test: `test_finalize_and_commit_moves_file_and_updates_job`'s
      summary-message assertion and `test_stats_dict_structure`'s key
      assertions were flipped to the new expectation first and confirmed to
      fail against the pre-fix code (RED) before the production change
      (GREEN). Full `tests/unit/services/data_ingestion/` suite (305 tests)
      passes; `make lint` clean.

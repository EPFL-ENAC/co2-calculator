---
status: in-progress
issue: 1661
last_updated: 2026-07-06
title: "SQL factor resolution for list sort/filter/pagination"
summary: "Replace the emission-FK factor join in get_submodule_data with a classification LATERAL join so factor-backed sort/filter/search work for every row (including not-yet-computed entries); delete the Python row-loop fallback."
---

## Problem

`get_submodule_data` joins `Factor` through emission rows
(`RollupEmission.primary_factor_id` / `min(primary_factor_id)` agg). Entries
without computed emissions get `Factor = NULL` **in SQL**: factor-backed
sort keys (`equipment.active_power_w`, buildings/cloud/process maps) sort
them last, filters miss them, and the Python resolver fallback fixes only
the displayed page — after pagination. Sort/search/pagination disagree with
what the table shows.

## Design

One correlated `LEFT JOIN LATERAL ... LIMIT 1` per entry row, built
generically from the handler's classification fields — the SQL twin of
`FactorResolver`, deterministic **because the Phase-2 reupload sweep
guarantees a single factor generation** per (det, year, classification):

- match: `f.data_entry_type_id = :det AND f.year = data_entries.year AND
  f.classification->>kind = data.data->>kind`
- subkind chain (plain handlers): accept exact subkind or subkind-less row;
  `ORDER BY (subkind matched) DESC` → exact wins, kind-only row is the
  fallback.
- override chain (purchase): accept override-code match or code-less
  (average) row; `ORDER BY (code matched) DESC, (code IS NULL) DESC` —
  override-first, then average. Ambiguity resolves to a deterministic pick
  (display layer; compute/update keep raising loudly via `FactorResolver`).
- Aliased to the `Factor` entity; handler `sort_map`/`filter_map`
  expressions referencing `Factor.*` are adapted onto the alias at query
  build (`ClauseAdapter`), so the four modules' maps stay untouched.

Scope of the swap: the buildings branch and the generic non-travel branch
(covers equipment, buildings, external_cloud_and_ai, process_emissions,
purchase, …). Travel and headcount branches keep the emission join — their
kind is derived at compute time (absent from `data`), their maps don't
reference `Factor`, and their factor display comes from computed emissions.

The Python row-loop resolver fallback in `get_submodule_data` becomes dead
and is deleted (the lateral answers for every lateral-covered row; the
remaining branches never benefited from it — kind absent from data).

Display-semantics note (accepted): tables show the *current* resolution,
not "factor used at last compute"; post-Phase-2 these converge on every
recalc.

## Steps

- [ ] 1. `_factor_lateral(handler, data_entry_type_id)` helper building the
  aliased lateral + adapted sort/filter maps; wire into the buildings and
  generic non-travel branches; delete the Python fallback + its resolver
  import if unused.
- [ ] 2. PG integration tests (`test_sql_factor_resolution_pg.py`): entry
  WITHOUT emission rows sorts/filters by factor-backed keys and displays
  the factor; kind-only fallback preference; purchase override preference;
  entry with emissions unchanged; travel list unaffected.
- [ ] 3. Retarget the two resolver-fallback unit tests in
  `test_data_entry_repo.py` (fallback deleted).
- [ ] 4. Focused verification (changed test files + `tests/unit/repositories`),
  ruff/mypy on touched files; PR stacked on #1719.

## Progress log

- 2026-07-06: plan written; branch `feat/1661-sql-factor-resolution`.

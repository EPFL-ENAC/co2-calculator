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

- [x] 1. (shipped as `_resolved_factor_id`) correlated **scalar subquery**
  instead of LATERAL: works on sqlite (unit tests) AND Postgres, joins the
  real `Factor` table so sort/filter maps need no adaptation at all; wired
  into the buildings and generic non-travel branches; Python fallback
  deleted. sqlite quirk pinned: correlated ORDER BY is rejected, so the
  specificity preference is the non-correlated `IS NOT NULL DESC` (within
  the WHERE-filtered candidate set, carrying a subkind/code IS the exact
  match).
- [x] 2. PG integration test (`test_sql_factor_resolution_pg.py`): entry
  WITHOUT emission rows sorts/filters by factor-backed keys and displays
  the factor; kind-only fallback preference; purchase override preference;
  entry with emissions unchanged; travel list unaffected.
- [x] 3. Retargeted the four resolver-fallback unit tests to seeded-row tests + new subkind-preference and duplicate-determinism pins in
  `test_data_entry_repo.py` (fallback deleted).
- [x] 4. Focused verification (changed test files + `tests/unit/repositories`),
  ruff/mypy on touched files; PR stacked on #1719.
- [ ] 5. Update path stops resolving (user-approved): replace
  `resolve_factor_if_changed` with a resolver-free
  `clear_dependent_fields_on_kind_change` (subkind + override-code cleared
  on kind change, nothing else); drop the update-path `populate_defaults`
  call (near no-op today: fills only still-empty fields).
- [ ] 6. Derived hour defaults (user-approved): equipment formula falls
  back to `factor.values` for missing usage hours (enable the sketch at
  equipment/schemas.py:218-221); stop seeding at create/CSV; delete
  `populate_defaults` + `factor_value_fields`. Form pre-fill keeps coming
  from `/factors/{det}/classes/{kind}/values`. Semantics owned: blank-hours
  entries track the factor's current defaults ("live default").

## Progress log

- 2026-07-06: plan written; branch `feat/1661-sql-factor-resolution`.
- 2026-07-06: steps 1-4 done (scalar-subquery design; 261 repo unit tests + PG test green).

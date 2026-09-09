fix(pipeline): dedup module-scoped recalcs on their own module

Phase A stopped two units collapsing into one another by dropping dedup
for module-scoped children entirely. That left the other half open: one
unit re-uploading the same module twice recomputed identical rows twice,
and the only thing making that safe rather than merely wasteful was that
`acquire_factor_recalc_lock` happens to carry no unit scope. Narrowing
that lock later — which #2527 Phase B proposes — would have turned it
into duplicate `data_entry_emissions` rows, a table with no unique
constraint to catch them.

Deferring it was the wrong call and the stated reason did not hold. The
blocker was said to be that the pinned id lives in a json blob, which
has no btree equality operator. A cast fixes that: the scoped partial
unique index keys on
`((meta -> 'config' -> 'carbon_report_module_ids')::jsonb)` alongside
the existing three columns. Verified against Postgres 16 — two units
insert, the same unit twice is rejected.

`DedupConfig` gains `scoped_config_key` so the pre-check binds the
pinned value rather than interpolating it, and `chain_job` now swaps a
scoped child onto `EMISSION_RECALC_SCOPED_DEDUP` instead of disabling
dedup. A reordered id list misses the dedup and does redundant work,
which is the safe direction — it can never drop a unit's recalc.

Also adds the guards that were missing around the original fix:

- the two `_pg` regression tests now run on PRs, not only nightly, so
  the thing standing between us and silent wrong totals actually gates
  something;
- a truth table pinning that `_pins_module_scope` and the SQL predicate
  classify a config identically, since the shared constant covers only
  the two SQL sites;
- a test that fails if the recalc lock gains unit scope while scoped
  dedup is absent;
- a WARNING when a scoped child is collapsed by the fleet-wide key,
  which is unreachable by construction and therefore a live canary.

2907 unit and 479 integration tests pass; the new scoped test fails with
the swap reverted.

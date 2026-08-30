# Code Review: PR #2541 — stop dropping module-scoped emission recalcs on dedup

**Branch:** `fix/2537-recalc-dedup-scope`
**Base:** `origin/dev`
**Latest commit reviewed:** `cd3871e16` — docs(pipeline): align dedup index docs with the unscoped-only predicate
**Date:** 2026-08-30
**Reviewer:** Claude (high-effort review, requested as the highest-risk PR in the queue)

---

## Verdict: SHIP WITH FIXES

The bug is real, the diagnosis is right, and the fix is the minimal correct one.
Both regression tests were independently reproduced as failing on `origin/dev` with
the exact assertion messages the PR body quotes, and the migration was independently
verified to produce an index byte-identical to the model's declaration — a stronger
proof than the one the PR offers.

One required change before merge, and it costs one comment line: **the safety of
this PR rests on an advisory lock that the very next phase of the same plan is
explicitly planning to narrow.** Nothing in the diff records that dependency.
Details in Finding 1.

Everything else is a nit or a named follow-up.

---

## What I verified, and how

Claims in a PR body are not evidence. These were re-run from scratch.

| Claim | Method | Result |
| --- | --- | --- |
| Both new tests fail on `origin/dev` | `git checkout origin/dev -- backend/app backend/alembic`, keep the new test file, run the module | **Reproduced.** 2 failed, 5 passed |
| …with the quoted assertion messages | read the failure output | **Exact match** (both strings, verbatim) |
| The tests pass on the branch | same module, branch code restored | 7 passed |
| Unscoped recalcs still dedup (incl. the concurrent `asyncio.gather` pin) | ran dedup + reupload-semantics + orphan-recovery + aggregation-dedup + `tests/unit/tasks/test_runner.py` | **27 passed** |
| The migration is generated and matches the model | `alembic upgrade head` into one scratch PG; `SQLModel.metadata.create_all` into another; diffed `pg_indexes.indexdef` | **Byte-identical.** See below |
| The migration round-trips | `alembic downgrade -1`, re-read `indexdef` | Restores the original `uq_emission_recalc_active` exactly |
| `make -C backend lint` (ruff + prettier) | run | pass — 580 files formatted, all checks passed |
| `make -C backend type-check` (ty) | run | pass |
| Root `make lint` / `make type-check` | run | **frontend fails for want of `node_modules`** (`Cannot find package 'eslint-plugin-vue'`, then ~2200 `TS2307 Cannot find module`). Environment, not code — the diff is backend-only |

Both DBs produce, character for character:

```
CREATE UNIQUE INDEX uq_emission_recalc_active_unscoped ON public.data_ingestion_jobs
  USING btree (module_type_id, data_entry_type_id, year)
  WHERE (((job_type)::text = 'emission_recalc'::text)
     AND (state = ANY (ARRAY['NOT_STARTED'::ingestion_state_enum, 'QUEUED'::ingestion_state_enum, 'RUNNING'::ingestion_state_enum]))
     AND (module_type_id IS NOT NULL) AND (data_entry_type_id IS NOT NULL) AND (year IS NOT NULL)
     AND (((meta -> 'config'::text) -> 'carbon_report_module_ids'::text) IS NULL))
```

and exactly one index matching `uq_emission_recalc%` exists after the upgrade — the
old one is gone, no orphan left behind.

**A note on the PR's own migration proof.** The PR argues the migration is generated
because a subsequent `alembic revision --autogenerate` came out empty. That proof is
partly circular: the PR itself (correctly) states that alembic *ignores* a changed
`postgresql_where` on a same-named index — which is why the rename was needed at all.
An empty autogenerate therefore proves the index **name and columns** match the model,
not the **predicate**. The predicate is the entire point of this PR. The `indexdef`
diff above is the check that actually closes it, and nothing in the test suite performs
it automatically (`test_alembic_migrations.py::test_make_db_create_then_db_migrate` runs
create→migrate; it does not compare the migrated schema against the model's metadata).
Not a blocker — the artifact is correct — but the PR should not claim the empty
autogenerate as the proof.

---

## Correctness analysis

### Can this drop or duplicate emission rows?

**Drop: no — it fixes a drop.** The bug is exactly as diagnosed. Since `a6dd48692`,
`ingestion_tasks.py:562-572` pins `config.carbon_report_module_ids` on the recalc child
of a unit-specific ingest, while `EMISSION_RECALC_DEDUP` kept deduping fleet-wide on
`(module_type_id, data_entry_type_id, year)`. Two units uploading the same slice
concurrently collapsed into one child; the second pipeline's `expected_recalc` was 0,
it reported success, and its rows never received `data_entry_emissions`. The reproduced
`origin/dev` failure is that bug, not a proxy for it.

**Duplicate: no, but only because of a lock the diff never mentions.** See Finding 1.

### Does the pipeline stay idempotent and re-runnable?

Yes. I traced the re-run path end to end:

- `emission_recalc_handler` → `EmissionRecalculationWorkflow.recalculate_for_data_entry_type`
  → `DataEntryEmissionService.bulk_replace_for_entries`, which is
  `delete_by_data_entry_ids(ids)` followed by `bulk_copy(rows)` — a full replace over
  the entry set the job owns, not an increment. Re-running recomputes the same set.
- Aggregation is likewise a full `recompute_stats`/`recompute_stats_many` read-and-rewrite,
  not an accumulate, so an extra recalc+aggregation chain cannot inflate
  `carbon_report_modules.stats`.
- Two **scoped** children for different units touch disjoint `carbon_report_module` row
  sets. The PR's core argument — that collapsing them is dropped work rather than
  deduplication — holds.
- Two **unscoped** children remain in the index and still collapse, both in the Python
  pre-check and in the concurrent `IntegrityError` path. The pre-existing
  `asyncio.gather` pin in `test_reupload_semantics_pg.py` still passes, so #1219's
  original guarantee is intact.

### Does the narrowed predicate open a double-write for the SAME module scope?

This is the sharp question, and the answer is **no today, by a mechanism the PR does
not name**.

Two scoped children with the *same* `carbon_report_module_ids` (one unit re-uploading
back-to-back) used to collapse and now both run. `bulk_replace_for_entries` is
DELETE-then-COPY with no unique constraint behind it — I checked, `DataEntryEmission`
has no `__table_args__` at all, so nothing at the DB level would reject duplicates. An
interleaving of `DELETE(e) / DELETE(e) / COPY(rows) / COPY(rows)` would produce doubled
emission rows: precisely the silent-wrong-total failure this PR exists to eliminate.

That interleaving is impossible today because `emission_recalc_handler` takes
`acquire_factor_recalc_lock(data_session, module_type_id=…, year=…)` —
`pg_advisory_xact_lock(1237, module_type_id * 100_000 + year)` — before the workflow
runs, and I confirmed `app/workflows/emission_recalculation.py` contains **no `commit()`
at all**, so the transaction-scoped lock is held across both `bulk_replace_for_entries`
call sites and released only when the runner commits `data_session`. Every recalc for a
given `(module_type_id, year)` therefore serializes, regardless of unit.

So the PR's follow-up item 1 ("duplicate work, not a correctness bug") is correct — but
its stated reason ("recalc is idempotent") is the weaker half of the argument. Serial
execution is what makes the idempotence sufficient.

### Other invariants that the old index used to guarantee

The old index guaranteed at most one active `emission_recalc` per `(module, det, year)`
fleet-wide. That is now false for scoped rows, so I checked every consumer that could
have been leaning on it:

- `pipelines.expected_recalc` (`repositories/data_ingestion.py:666`) counts
  `emission_recalc` rows **within one pipeline**. Unaffected.
- `_is_last_recalc_sibling` gates on `pipeline.expected_recalc` under
  `SELECT pipelines … FOR UPDATE`, scoped to the pipeline. Unaffected.
- `compute_pipeline_progress` reads the same per-pipeline counter. Unaffected.
- `claim_job` uses `ix_data_ingestion_jobs_is_current_unique`, a different index.
  Unaffected.

No consumer selects "*the* active recalc for a scope". Clean.

---

## Findings

### 1. REQUIRED — pin the advisory-lock invariant this fix now depends on

`backend/app/tasks/_chain.py:316-325`

Dropping dedup for scoped children is safe **only** while
`acquire_factor_recalc_lock` keys on `(module_type_id, year)` with no unit scope, so
that two scoped recalcs for the same `carbon_report_module_id` cannot interleave their
DELETE/COPY. Nothing in the diff says so.

This is not hypothetical. The #2527 plan (issue/PR #2537), of which this PR is Phase A,
names that same lock as a dominant cost:

> the factor advisory lock keys on `(module_type_id, year)` with no unit scope, so
> unrelated units' uploads serialize head-to-tail

Narrowing that lock is an obvious Phase B move, and it is the one change that turns
this PR's "duplicate work" follow-up into duplicated `data_entry_emissions` rows with
no constraint to catch them. The Phase B author needs to trip over this invariant, and
the place they will be reading is the branch they are about to change, not this review.

Add two lines where dedup is dropped, e.g.:

```python
# Safe only while acquire_factor_recalc_lock keys on (module_type_id,
# year) with NO unit scope: two scoped children for the SAME module
# would otherwise interleave bulk_replace_for_entries' DELETE/COPY and
# duplicate emission rows (data_entry_emissions has no unique index).
# Narrowing that lock (a #2527 Phase B candidate) requires restoring
# dedup for identical scopes first.
```

A mirroring line in `app/tasks/_locks.py` would be cheap insurance too.

### 2. LATENT — "key present" and "actually scoped" are not the same thing

`backend/app/tasks/_chain.py:162-170`, `app/tasks/emission_recalculation_tasks.py:367-374`,
`app/repositories/data_entry_repo.py:519`

The shared `EMISSION_RECALC_UNSCOPED_SQL` constant does exactly what it claims: the
index and the Python pre-check cannot drift, and `_pins_module_scope` deliberately tests
key *presence* so that it agrees with `meta -> … IS NULL` row for row — including the
subtle case where a JSON `null` is not SQL `NULL`. I checked that correspondence and it
is right, including for `[]` and for an explicit `null`.

What the constant does **not** cover is the third reader — the handler that consumes the
scope:

| `config` | `_pins_module_scope` | in the index? | what the handler recomputes |
| --- | --- | --- | --- |
| absent | False | yes (dedups) | whole slice |
| `[101]` | True | no (no dedup) | module 101 |
| `[]` | True | **no (no dedup)** | **whole slice** — `data_entry_repo.py:519` is `if carbon_report_module_ids:`, falsy |
| `"101"` (non-list) | True | **no (no dedup)** | **whole slice** — `isinstance(raw_scope, list)` is False → `module_scope = None` |

The bottom two rows are children the dedup layer treats as narrow and disjoint while the
handler treats them as whole-slice. Today that is unreachable: the only producer
(`ingestion_tasks.py:565-572`) guards on `raw_module_id is not None` and always emits
exactly one int. So this is a trap, not a bug — but it is the drift the shared constant
does not prevent, and it is worth one line in the `_pins_module_scope` docstring saying
that a *present but empty or non-list* scope is a caller error, not a supported input.

### 3. NIT — the `nosec B608` justification is now incomplete

`backend/app/tasks/_chain.py:498-502`

The comment justifies the f-string interpolation by naming only `dedup_config.scope_columns`.
`extra_predicate` is now interpolated into the same statement. It is equally a compile-time
constant on the same frozen dataclass, so the justification still holds in substance — but a
future reader auditing the `nosec` will find the comment does not describe what is actually
interpolated. One clause fixes it.

### 4. NIT — rollout window (informational, no action needed)

`app/db.py:47-55` rewrites the DSN to `postgresql+psycopg`, and the helm README's example
`DB_URL` confirms psycopg in deployment. Under psycopg, `exc.orig.diag.constraint_name`
is populated, so the structured branch of the `IntegrityError` catch is the live one —
the substring fallback (under which the old name would still match the new one as a
prefix) does not apply.

Consequence during a rolling deploy, after the migration but before all pods are
replaced: an old pod that loses a race on the renamed index reads
`uq_emission_recalc_active_unscoped`, compares it against its compiled-in
`uq_emission_recalc_active`, and re-raises instead of returning the dedup signal — the
job lands FINISHED+ERROR. Old pods also keep their un-narrowed pre-check, so the
original bug persists for them until they are gone.

Neither corrupts data, and a loud job error is this repo's preferred failure mode over a
silent skip. Worth knowing, not worth changing.

### 5. NIT — DDL locking

`op.drop_index` / `op.create_index` without `CONCURRENTLY` take `ACCESS EXCLUSIVE` on
`data_ingestion_jobs` for the duration. The index this replaces was originally created
`CONCURRENTLY` (per plan 310-post-merge-fix-batch:185) precisely to avoid that. On a jobs
table this is likely milliseconds, and generated migrations shouldn't be hand-edited into
`CONCURRENTLY` without also setting `transaction_per_migration=False` — so this is a
deliberate-tradeoff note, not a change request. If the migration runs against a busy
stage/prod, expect a brief write stall on that table.

### 6. NIT — `chain_job` length (pre-existing, marginally worse)

`chain_job` is 119 code lines excluding docstring and comments; `_insert_child_with_dedup`
is 102. Both were far past the ≤40-line rule before this PR, which adds ~5 lines to one
and ~2 to the other. Flagging for the record only — splitting either is out of scope for
a correctness fix on pipeline internals, and the guardrails explicitly discourage
opportunistic refactors here.

---

## Repo-invariant checklist

| Invariant | Result |
| --- | --- |
| No silent fallbacks | **Pass, and improved.** This PR removes one: a dedup-skipped recalc that reported success. The `_pins_module_scope` opt-out is unconditional and commented, not a swallow. The pre-existing `except TypeError, ValueError` at `ingestion_tasks.py:568` logs and degrades to an unscoped recalc, which is the safe direction (recompute more, not less) — and is valid Python 3.14 (PEP 758), not a syntax error |
| Functions ≤40 lines, ≤2 nesting | Nesting fine (≤2 in every touched block). Length: see Finding 6 — pre-existing |
| Imports at top | **Pass.** The one new import (`EMISSION_RECALC_UNSCOPED_SQL`) is added to the existing top-of-file `app.models.data_ingestion` block. No new inline imports |
| `col()` on SQLModel column refs | **N/A.** The touched code is raw `text()` SQL and `Index()` declarations; no new ORM column comparisons |
| No `# type: ignore` / `@ts-expect-error` | **Pass.** None added |
| Migrations generated, not hand-authored | **Pass.** Autogenerate markers intact, one `drop_index` and it is the index being replaced (no false positives), and the produced index matches the model byte for byte. The rename rationale is sound and correctly explained |
| Bug fix ships a regression test | **Pass, and verified failing without the fix** — both tests, both messages |
| Backend is source of truth / layering | **N/A** — no route or service boundary touched |
| No backward-compat paths | **Pass.** The old index is dropped, not kept alongside. (The unrelated `dedup_active` deprecation shim is pre-existing) |
| Docs updated with the rename | **Pass.** `alembic/CUSTOM_DB_OBJECTS.md` and `10-INTEGRATION-TESTING.md` updated; historical plans and code-reviews correctly left alone. The PR already flags `2211-consolidate-alembic-files.md:182` as needing the new name whenever that consolidation runs |

---

## Follow-ups to open as issues (not blockers)

1. **Re-collapse identical scoped children.** Two scoped children with the *same*
   `carbon_report_module_ids` now both run. Correct but wasteful, on exactly the path
   Phase A is about to be measured on. Needs a jsonb-expression unique index; the plan
   deliberately chose the simpler path. Agreed with the PR that this is a follow-up.
2. **A unique index on `data_entry_emissions`.** The only thing standing between a
   narrowed advisory lock and duplicated emission rows is serialization. A DB-level
   uniqueness guarantee would make the whole class of bug structurally impossible and
   would retire Finding 1's dependency. Sizeable change; worth an issue, not this PR.
3. **Automate the model-vs-migration index-predicate check.** `pg_indexes.indexdef`
   diffing between an `alembic upgrade head` DB and a `create_all` DB is ~15 lines of
   test and would have made this PR's migration proof self-evident. It would also catch
   the next partial-index predicate drift, which is a failure mode this repo has now hit
   twice.
4. **Sweep the existing damage.** The plan's third Phase A checkbox — entries in the perf
   window with no `data_entry_emissions` under a FINISHED pipeline — is not addressed here
   and must not be, per the PR's own note. Repair by re-running the module-scoped recalc,
   never by widening a read query.

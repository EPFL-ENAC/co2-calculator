# Code review — PR #2543 `perf(emissions): denormalize module/type join keys onto data_entry_emissions` (#2527)

- **Branch:** `wip/2532-kg-co2eq-denormalization` @ `d82b69b6`
- **Base:** `origin/dev`
- **Plan:** `docs/src/implementation-plans/2527-denormalize-emissions-module-key.md` (`status: delivered`)
- **Reviewed:** 2026-08-30, HIGH effort, with empirical verification against throwaway Postgres containers

## Verdict: SHIP WITH FIXES

The design is right and the implementation is correct. Every load-bearing claim in the
PR description held up under checking, and two of them I verified empirically rather
than by reading: the COPY column ordering and the migration backfill.

The fixes are not in the shipped code — they are in the **test that guards it** and in
**where that test runs**. As it stands, the single guard against a silent
value-mis-assignment (a) cannot detect the specific transposition it was written for,
and (b) does not execute on pull requests at all. Both are cheap to fix and neither
requires touching the production diff.

---

## 1. The positional COPY path — the most important check

`_EMISSION_COPY_SQL`'s column list and `bulk_copy`'s `copy.write_row` tuple must agree
in order. They do — 10 positions, exact match:

| # | `_EMISSION_COPY_SQL` | `write_row` tuple |
|---|---|---|
| 1 | `data_entry_id` | `e.data_entry_id` |
| 2 | `emission_type_id` | `e.emission_type_id` |
| 3 | `primary_factor_id` | `e.primary_factor_id` |
| 4 | `kg_co2eq` | `e.kg_co2eq` |
| 5 | `additional_value` | `e.additional_value` |
| 6 | `scope` | `e.scope` |
| 7 | `meta` | `Json(e.meta) if …` |
| 8 | `computed_at` | `e.computed_at` |
| 9 | `carbon_report_module_id` | `e.carbon_report_module_id` |
| 10 | `data_entry_type_id` | `e.data_entry_type_id` |

### The test was executed, and it passes

The PR admits `test_emission_bulk_copy_lands_every_column_in_its_own_place` was
collected but never run. I ran it, against a throwaway `postgres:16-alpine` container
the fixture spins up on `localhost:55432` (never a shared DB — `backend/.env` does not
exist in this worktree, so nothing could fall through to the dev database):

```
uv run pytest tests/integration/services/data_ingestion/test_bulk_copy_pg.py \
  -k emission_bulk_copy -q -p no:randomly
→ 2 passed, 4 deselected in 5.68s
```

Both new tests pass: the positional test and `test_emission_bulk_copy_rejects_unstamped_row`.

### FINDING 1 (HIGH) — the positional test cannot catch the one swap it exists for

A green test only means something if it would go red on the failure it guards. So I
mutation-tested it.

**Mutation A — swap the two new columns**, i.e. exactly the mistake the test was
written to catch:

```python
# backend/app/repositories/data_entry_emission_repo.py, write_row tuple
-    e.carbon_report_module_id,
     e.data_entry_type_id,
+    e.carbon_report_module_id,
```

```
→ 2 passed, 4 deselected in 2.39s
```

**The test still passes with the columns transposed.**

**Mutation B — swap `kg_co2eq` / `additional_value`** (control, to prove the test is
not simply inert):

```
→ FAILED … assert 34.5 == 12.5
   1 failed, 1 passed
```

So the test works in general and has one blind spot — precisely on the pair this PR adds.

**Root cause.** The docstring asserts *"Every value here is distinct so a swap cannot
pass."* That is false in the fixture's own environment. The `pg_dsn` fixture
`drop_all`/`create_all`s a fresh schema per test, so sequences restart at 1:

- `entry.id` → **1** (position 1)
- `module.id` → **1** (position 9)
- `DataEntryTypeEnum.member.value` → **1** (position 10)

Three of the ten positions hold the integer `1`. Any permutation among positions
1, 9 and 10 is invisible to this test — and 9/10 is the adjacent pair a future edit is
most likely to transpose.

**Fix — and note it must cover all three colliding positions, not just the new pair.**
Making only `carbon_report_module_id` and `data_entry_type_id` differ still leaves
`data_entry_id` (position 1) equal to `module.id` (position 9), so a 1↔9 transposition
would keep passing. All three must be distinct, guarded by an assertion so the property
cannot rot back as sequences shift:

```python
# positions 1, 9 and 10 all carry a bare int — they must differ, or a
# transposition among them lands values in the wrong columns undetected
assert len({entry.id, module.id, emission_type_id_value}) == 3
```

The exact seeding arrangement is the author's call — e.g. use
`DataEntryTypeEnum.student` (2) for the entry and burn a row or two so `entry.id` and
`module.id` diverge. The load-bearing part is the assertion covering three positions.
Asserting `computed_at` (currently written but never read back) would close position 8
as well.

This is a test defect, not a code defect. The shipped ordering is correct today. But
the test is the only thing standing between a future one-line edit and silently
mis-assigned emission data, and right now it does not stand there.

### FINDING 2 (HIGH) — the COPY test never runs on a pull request

`.github/workflows/test.yml` → `make test-cov-xml` → `backend/Makefile:114`:

```
$(PYTEST) tests/unit --cov=app --cov-report=xml …
```

`tests/unit` only. The integration suite is `make test-cov-xml-integration`
(`Makefile:119`), invoked from `.github/workflows/integration-tests.yml`, whose triggers
are `schedule: cron "30 3 * * *"`, `workflow_dispatch`, and `push: ci-test/**`.

So the PR's **15/15 green checks did not execute `test_bulk_copy_pg.py`.** The only
guard on a silently mis-assigning COPY runs up to 24 hours later, on `dev`, after the
merge — and never on the PR whose diff changes the tuple.

Combined with Finding 1, the current state is: the guard is blind to the relevant
mutation *and* would not have run anyway.

Options, cheapest first:

1. Add the two emission COPY tests (or the whole `test_bulk_copy_pg.py` file) to the PR
   job the way `test-backend-migrations` already does for
   `tests/integration/test_alembic_migrations.py` — that job is precedent for "one
   integration file, scoped so it stays fast on PRs."
2. Or a path-filtered job: run `tests/integration/services/data_ingestion/test_bulk_copy_pg.py`
   when `data_entry_emission_repo.py` or `data_entry_repo.py` changes.

Whichever — a positional COPY with no PR-time guard is a foot-gun with the safety
catch taped down.

---

## 2. Are all write paths stamped? — Yes

The plan names four. I swept for a fifth and found none.

**`DataEntryEmissionRow(` construction sites in `backend/app/`:** exactly four —
`data_entry_emission_service.py:619, 649, 707, 739`. All four are inside
`prepare_create` (lines 388–756). The stamp loop is at 751–755, immediately before
`return results` at 756. The only other `return` in the function is `return []` at 542
— an empty list, nothing to stamp. No path can leave the function with an unstamped row.

**`DataEntryEmission(` construction in `backend/app/`:** one, in `to_orm()`
(`data_entry_emission.py:296`), which raises when either key is `None`.

**Every service-level write API routes through `prepare_create`:**

| API | Path |
|---|---|
| `create` | `prepare_create` → `to_orm()` → `repo.bulk_create` |
| `upsert_by_data_entry` | `prepare_create` → `to_orm()` → `repo.bulk_create` |
| `bulk_replace_for_entries` | callers pass `prepare_create` output → `repo.bulk_copy` |

Callers checked: `workflows/emission_recalculation.py:159/227/244`,
`services/simulator_plan_service.py:924/969`,
`services/carbon_report_module_service.py:401`,
`workflows/carbon_report_module.py:300/523`. All stamped.

**Planner copies — no re-pointing.** The claim "planner copies included" holds:
`SimulatorPlanService._prepare_recalc_emissions` calls
`prepare_create(DataEntryResponse.model_validate(entry))` per entry, so the keys come
from the *target* entry, not a source entry. A grep for post-hoc `.data_entry_id =`
assignment on emission rows returns nothing — no path builds rows against one entry and
writes them under another id. This was the finding that could have sunk the PR; it is
clean.

`DataEntryResponse` inherits `carbon_report_module_id` and `data_entry_type_id` from
`DataEntryBase`, both `int` and `nullable=False`, so the stamp source is never `None` on
either accepted input type.

**Seeder (raw asyncpg, bypasses the ORM).** `generate_emissions_for_entry` returns a
10-tuple in exactly `tmp_emissions`'s DDL order, which matches the
`INSERT … SELECT *` column list. The call site
(`seed_data_entries.py:723–728`) passes `data_entry_rows[idx][1]`, the module id, per
the documented positional contract of `generate_data_entries_for_module`
(`(data_entry_type_id, carbon_report_module_id, data, status)`). Correct.

### FINDING 6 (NIT) — two unstamped-capable public APIs with no callers

`DataEntryEmissionService.bulk_create(list[DataEntryEmission])` (line 1096) and
`DataEntryEmissionService.bulk_copy(list[DataEntryEmissionRow])` (line 1103) have no
callers anywhere in `backend/app/`. They are the only emission-write entry points that
do not route through `prepare_create`. `bulk_copy` at least raises on an unstamped row;
`bulk_create` takes already-materialized ORM rows and would let a caller through with
whatever it built. Deleting both removes the fifth-construction-site risk structurally
rather than by convention — and the repo's own "no backward-compat paths / delete the
old way" rule already asks for it.

---

## 3. The T5 trap — no narrowing was lost

`page_entry_ids` did double duty, and the rewrite keeps both jobs. The reasoning
depends on the guard at `data_entry_repo.py:1004`:

```python
if not is_travel_entry and not is_buildings_entry and not is_headcount_entry:
    page_entry_ids = await self._page_first_entry_ids(...)
```

So `page_entry_ids` is `None` for travel, buildings and headcount. Working through each
branch:

- **Generic branch (`else`, incl. travel).** Old: `data_entry_id IN (module_entry_ids)`,
  where `module_entry_ids` was narrowed by `page_entry_ids` when non-`None`. New:
  `emission_scope` **plus** `data_entry_id = ANY(page_entry_ids)` re-applied at
  1164–1173. **Narrowing kept.** For travel (`page_entry_ids is None`) both old and new
  reduce to module+type scope. Equivalent.
- **Buildings legacy aggregate.** `page_entry_ids` is always `None` here, so the old
  `module_entry_ids` was *never* narrowed in this branch. Replacing it with
  `emission_scope` is exactly equivalent. **Nothing lost** — this is the trap, and the
  PR did not fall into it.
- **Headcount.** No standalone aggregate; the rollup `JOIN` gained the module/type
  predicates and is mirrored verbatim into `count_factor_joins` via the shared
  `rollup_on` variable. Both the page query and the count apply it with `isouter=True`
  (`data_entry_repo.py:1408`), so the count cannot degenerate.
- **`get_professional_travel_trip_legs`.** Old: `IN (SELECT id FROM data_entries WHERE
  carbon_report_module_id = m)`. New: `carbon_report_module_id == m` on the emission
  row. No type predicate in either — both travel modes wanted, as documented. Equivalent.

The old `module_entry_ids` subquery carried no predicates beyond module and type (no
soft-delete, no source filter), so `emission_scope` is a faithful substitution given the
denormalized keys are accurate — which §2 and §4 establish.

Extracting `rollup_on` into a variable used by both the page query and
`count_factor_joins` is a genuine improvement: the previous duplicated on-clause was the
kind of thing that drifts.

---

## 4. The migration — verified on populated data

Nullable → backfill → `SET NOT NULL` → `CREATE INDEX` in one migration is an approved
maintainer decision (the DB is dropped for this change), so the rolling-pod hazard is
out of scope. What remained to check was whether the backfill is *correct* and whether
the file was generated.

**Generated, not hand-authored.** The `# ### commands auto generated by Alembic` markers
are intact, the revision id/filename follow `make db-revision`'s timestamp convention,
and `down_revision` chains correctly to `95fe938000d4`. The documented adjustment
(autogenerate emits `nullable=False`, which cannot be added to a populated table) is the
standard, expected edit and is explained in the docstring.

**Backfill verified empirically.** `tests/integration/test_alembic_migrations.py` only
runs `upgrade head` on an *empty* DB, where the backfill `UPDATE` touches zero rows — so
it proves nothing about the backfill. I ran that suite (`2 passed in 7.98s`) and then
built the missing case: a throwaway `postgres:16-alpine` on port 15445, migrated to
`95fe938000d4`, seeded **two** entries in **two different modules with two different
types** (so a constant-value or cross-joined backfill could not pass), then
`upgrade head`:

```
expected: {1: (1, 1), 2: (2, 2)}
got     : {1: (1, 1), 2: (2, 2)}
index   : CREATE INDEX ix_dee_module_type_entry ON public.data_entry_emissions
          USING btree (carbon_report_module_id, data_entry_type_id, data_entry_id)
          INCLUDE (kg_co2eq, emission_type_id, primary_factor_id, scope)
notnull : [('carbon_report_module_id', True), ('data_entry_type_id', True)]
RESULT: PASS
```

Backfill correct, `NOT NULL` applied, index created with the exact `INCLUDE` list from
the model. The `UPDATE … FROM data_entries WHERE de.id = dee.data_entry_id` cannot leave
a NULL behind: `data_entry_id` is `nullable=False` with `ON DELETE CASCADE`, so no
orphan emission can exist — the docstring's argument checks out.

**Seeder DDL byte-equivalence.** Postgres reports the index as `USING btree (…) INCLUDE
(…)`; `seed_post_all.py`'s hand-written DDL is the same column list and same `INCLUDE`
list in the same order, so autogenerate will not churn. Documented in
`CUSTOM_DB_OBJECTS.md`. Good.

**Nit:** the repo already has the pattern for testing a data migration on populated data
— `test_2458_orphaned_explore_cleanup` migrates to a pinned pre-revision, seeds, applies,
asserts. The backfill has no such test. Given the DB is being dropped this time it is not
worth blocking on, but the next data migration should reuse that harness.

### FINDING 3 (MEDIUM) — two plan items not delivered

Issue #2527's implementation checklist, item 3, reads: *"…drop the `module_entry_ids`
IN-subquery. **Same for the rollup join and module stats sums.**"*

The rollup joins were done. The module stats sums were not:
`DataEntryEmissionRepository.get_stats` still reaches the module through
`data_entries`:

```python
.join(DataEntry, col(DataEntryEmission.data_entry_id) == col(DataEntry.id))
.where(DataEntry.carbon_report_module_id == carbon_report_module_id, _is_leaf_emission())
```

This runs on the module GET path (`api/v1/carbon_report_module.py:354`) and on every
`recompute_stats`. It is not a mechanical substitution — the
`exclude_planner_snapshots` branch genuinely needs `DataEntry.source` — but the common
case can filter on the emission row's own key and keep the `DataEntry` join only when
that flag is set.

Also unshipped: the plan's "bonus", a composite `(carbon_report_module_id,
data_entry_type_id)` index on `data_entries`, described as "a cheap add-on in the same
migration" to fix the BitmapAnd on the entries side.

Neither blocks this PR. Both should be an explicit follow-up issue rather than a silent
omission, since the plan is marked `status: delivered` and a reader will take that to
mean the checklist was completed. Either ship them or note the deferral in the plan.

---

## 5. Repo invariants

**No derived values stored on entries — correct.** `kg_co2eq` stays in
`data_entry_emissions` where recalc owns it. The two new columns are copies of the
parent's module and type: join keys, not computed values. This also mirrors an existing
precedent in the same codebase — `DataEntry.year` / `DataEntry.unit_id` are denormalized
from `carbon_report` with an almost identical comment ("immutable facts of an entry;
entries never move between modules"). Mirroring beats inventing; good.

Skipping the `ForeignKey` on `carbon_report_module_id` is justified (cascade already
covers deletion via `data_entry_id`; a per-row constraint check would tax the COPY hot
path) and is a deliberate, documented trade rather than an oversight.

### FINDING 4 (LOW) — "no re-parenting path anywhere" is overstated

The PR states: *"an entry's module and type are set at construction and never change
(verified: no `update(DataEntry)`, no raw `UPDATE data_entries`, no re-parenting path
anywhere)."* The raw-SQL half is true — there is no `UPDATE data_entries` anywhere. The
ORM half is not:

```python
# data_entry_repo.py:348-354
update_data = data.model_dump(exclude_unset=True)
for field, value in update_data.items():
    ...
    setattr(db_obj, field, value)
```

`data: DataEntryUpdate` extends `DataEntryBase`, which declares
`carbon_report_module_id` and `data_entry_type_id` as **required** fields — and
`DATA_ENTRY_META_FIELDS` deliberately keeps them top-level rather than folding them into
`data`. So they are always present in `model_dump(exclude_unset=True)` and are
`setattr`-ed on every update. A payload naming a different module would re-parent the
entry.

What actually makes this safe is the caller, not immutability: the sole caller of
`DataEntryService.update` is `CarbonReportModuleWorkflow` (line 509), which calls
`upsert_by_data_entry` twenty lines later — deleting the entry's emissions and
re-stamping them from the updated entry, in the same transaction. The outcome is
correct; the stated reason is not.

Worth correcting in the model comment and the plan, because the two arguments have
different failure modes. "Immutable" implies nothing can go wrong. "The one update path
re-stamps" tells the next author what they must preserve: **any future path that changes
an entry's module or type without recomputing its emissions leaves the denormalized keys
stale, and every query in this PR now trusts them** — the rows silently drop out of the
aggregate rather than raising. Given the codebase's "no silent fallbacks" rule, that
constraint deserves to be written down where someone will hit it.

### FINDING 5 (LOW) — `Any` in and `Any` out

```python
def _emission_module_scope(emission: Any, module_id: int, type_id: int) -> Any:
```

No `# type: ignore` is used anywhere in the diff, which satisfies the letter of the rule.
But `Any` on both ends is the same escape hatch by another name — it is here to dodge
`aliased()`'s typing. The return is a `ColumnElement[bool]`, and the file already imports
that (`data_entry_emission_repo.py` uses it for `_is_leaf_emission`). Annotating the
return costs nothing; the `aliased()` parameter is the genuinely awkward half and can
stay.

**Other style checks:** `col()` is used on every SQLModel column reference in the new
code. The new helper is 8 lines. `prepare_create` is 368 lines against the ≤40 rule —
badly over, and it already carries a `TODO: Make this function readable!` — but that is
pre-existing and this PR adds 7 lines to it. Not this PR's debt; noted only so it is not
mistaken for newly introduced.

**Test-suite hygiene:** replacing ~44 hand-written `DataEntryEmission(...)` constructions
with one `make_emission(entry, **kw)` factory that derives both keys from the parent is
the right call — one helper instead of 44 chances to get it wrong, and the docstring on
`make_data_entry_emission` correctly warns that its synthetic defaults will fall outside
a module-scoped query. Confirmed: zero `DataEntryEmission(` constructions remain in
`backend/tests/` outside `conftest.py` and two intentional `DataEntryEmissionRow(` uses
in the COPY tests.

`test_submodule_kg_sort_scope.py` is a good test — decoys in every case (another module
with the same type, another type in the same module), all three `kg_sort_expr` branches,
and the headcount branch asserted through ordering because the response does not expose
`kg_co2eq`. It runs on SQLite, so it validates the predicate logic, not the index; that
is the right split.

---

## Verification performed

| Check | Result |
|---|---|
| `pytest -k emission_bulk_copy` (Docker PG, throwaway) | **2 passed** |
| Mutation A: swap the two new COPY columns | **passes — test blind (Finding 1)** |
| Mutation B: swap `kg_co2eq`/`additional_value` | fails correctly (control) |
| `pytest tests/integration/test_alembic_migrations.py` | 2 passed |
| Migration backfill on populated data, 2 distinct (module, type) pairs | **PASS** — backfill, `NOT NULL`, index all correct |
| `tests/unit/repositories` + emission service (incl. new test file) | 320 passed |
| `make lint` (backend) | All checks passed |
| `make type-check` (backend) | All checks passed |
| `make lint` (frontend) | fails on missing `node_modules` in this fresh worktree; PR touches **0** frontend files |
| `# type: ignore` / `@ts-expect-error` in diff | none |

All Postgres work ran in throwaway containers (`postgres:16-alpine`, ports 55432 /
15445), created and torn down by the fixtures. No shared database was touched;
`backend/.env` does not exist in this worktree, so nothing could fall through to dev.

---

## Required before merge

1. **Fix the positional test's blind spot** (Finding 1) — in
   `test_emission_bulk_copy_lands_every_column_in_its_own_place`, make `entry.id`,
   `module.id` and `data_entry_type_id` (positions 1, 9, 10) three *distinct* integers,
   and assert the distinctness so it cannot regress. Fixing only the new pair leaves the
   1↔9 transposition undetected. Re-run mutation A to confirm it now fails.
2. **Make that test run on PRs** (Finding 2) — mirror the `test-backend-migrations` job
   pattern, or add a path-filtered job. A positional COPY guarded only by a nightly job
   is not guarded.

## Follow-up (do not block)

3. File an issue for the two unshipped plan items (Finding 3): `get_stats` still joining
   through `data_entries`, and the `data_entries (carbon_report_module_id,
   data_entry_type_id)` composite index — or record the deferral in the plan, which
   currently reads `status: delivered`.
4. Correct the "never re-parented" wording (Finding 4) to name the real guarantee: the
   sole update path re-stamps emissions, and any future path that does not will silently
   desync the keys.
5. Annotate `_emission_module_scope`'s return as `ColumnElement[bool]` (Finding 5).
6. Delete the uncalled `DataEntryEmissionService.bulk_create` / `.bulk_copy`
   (Finding 6) — the only emission-write APIs that bypass `prepare_create`.

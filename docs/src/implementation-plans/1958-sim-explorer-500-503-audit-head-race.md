---
status: delivered
issue: 1958
last_updated: 2026-08-18
title: "Sim Explorer 500/503 — READ audit on a GET"
summary: "The 500 was a GET writing a version-chained audit row keyed on carbon_report_module_id: two parallel submodule fetches of one module collided on audit_document_one_current_idx. Fixed by deleting the READ audit and scoping audit off Simulator entries; both locks (advisory and savepoint-retry) removed as unnecessary."
---

# 1958 — Sim Explorer 500 / 503

## Root cause

`data_entry_service.get_submodule_data` (`data_entry_service.py:706-742`)
writes an audit row **on a GET**:

```python
# for headcount and travel (plane/train), keep a READ audit record
await self.versioning.create_version(
    entity_type="CarbonReportModule",
    entity_id=carbon_report_module_id,
    data_snapshot={},  # No snapshot for read operations
    change_type=AuditChangeTypeEnum.READ,
    ...
)
```

The route is `GET /{carbon_report_id}/modules/{module_id}/{submodule_id}`
(`carbon_report_module.py:671`). The audit key is the **module** id, not the
submodule — and plane, train and member are submodules that share one
`carbon_report_module_id`. A page that loads the Travel module fetches the
plane and the train submodule in parallel, so two concurrent requests do the
same read-modify-write on the same audit head:

```
GET …/travel/plane ─┐
                    ├─► create_version("CarbonReportModule", 42) ─► head swap on 42
GET …/travel/train ─┘
```

Both read head version N, both flip `is_current=False`, both insert
`is_current=True` — and the loser trips
`audit_document_one_current_idx` (unique on `(entity_id, entity_type) WHERE
is_current`, `app/models/audit.py:140-146`). That is the 500.

`#1959`'s advisory-lock comment named this exact scenario. It was right about
the mechanism and wrong about the layer.

**Why the Explorer surfaces it more than the Calculator:** #1959 also
parallelised `prefetchSubmoduleCounts()` and `fetchEmissionBreakdown()` on
`SimulationExplorePage.vue`, which widens the window the same PR's lock was
trying to close.

**The 503 has no trace.** But a GET that opens a write transaction, blocks on
a lock held by its own sibling request, and schedules an Elasticsearch sync
task is a strong candidate for pool exhaustion under a page that fires
several of them at once. Treat it as unconfirmed until traced; do not close
#1958 on a 503 claim without one.

## Why this audit record is wrong regardless of the race

`AuditDocument` is a _version chain_: `version`, `previous_hash`,
`current_hash`, `data_diff`, and an `is_current` head. Those exist to make
mutations tamper-evident. A read has none of that shape:

- `data_snapshot={}` every time, so `_compute_diff` returns `None` on every
  row — the diff column is dead weight.
- The hash chain hashes empty dicts. It proves nothing.
- Every page view increments `version` and swaps the head. Opening the Travel
  module ten times writes ten versions and ten head swaps for one module.
- It makes a GET non-idempotent and serializes parallel reads of the same
  module against each other.

If read-access logging is required (plausible — travel and headcount are
personal data), it is an **append-only log**, not a version chain. No
`is_current`, no head swap, no unique index, therefore no race and no lock.

## Delivered

### PR #1959 — merged, commit `46d85914`

- `data_entry_repo`: catch `ValidationError` per row in the submodule
  listing, log and skip the malformed entry, return `count=len(items)`.
  Fixes a second, unrelated 500. Note this is a silent-fallback shape — a
  skipped entry vanishes from a total. Acceptable only while the
  `logger.warning` names the id; if the same rows keep recurring, repair the
  stored data instead of skipping it.
- `audit_service`: `IntegrityError` was imported from `sqlite3`, so the
  `except` never matched the SQLAlchemy exception. Real bug, correctly fixed.
- `audit_service`: `pg_advisory_xact_lock(hashtext("<type>:<id>"))` around
  the head swap. Serializes the symptom; see below.
- Frontend: skeleton until `breakdownReady`; `workspaceGuard` forces a
  workspace reload when leaving a Simulator route. Both fix stale-data
  flashes, not the errors.

### PR #1961 — merged

`ModuleTable.vue` select editors commit on `@update:model-value` instead of
`@blur`. Unrelated to the READ-audit race (that path is `update`, keyed on
the entry id), but it does raise PATCH volume from the Explorer — worth
keeping in view if the 503 turns out to be pool pressure.

## Reverted on this branch: both locks

PR #2139 replaced the advisory lock with `session.begin_nested()` plus up to
5 retries on an `IntegrityError` matching `audit_document_one_current_idx`.
It is reverted here, and the `pg_advisory_xact_lock` it replaced is removed
too. Neither is needed once reads stop writing.

Why the retry was the wrong tool, recorded so it is not re-proposed:

1. **It serialized a write that should not exist.** The contention was
   manufactured by version-chaining a read.
2. **Its rationale argued against the wrong thing.** "`FOR UPDATE` can't
   cover the no-head case" is accurate about `get_current_version`'s
   `with_for_update()` — and an argument _for_ the advisory lock, not
   against it. Covering the no-head case is exactly what a key-based
   advisory lock does: there is no row to lock, so you lock the key.
3. **It left half the path open.** `bulk_create_versions`
   (`audit_service.py`) does the identical read-modify-write — batch-select
   heads, flip `is_current=False`, bulk-insert new heads — with no lock, no
   savepoint, no retry. Neither mechanism ever guarded it.
4. **It did not help the 503.** Both designs make the loser wait for the
   winner's commit while holding its DB connection — one in
   `pg_advisory_xact_lock`, the other blocked on the unique index during
   `INSERT`. Same connection, same duration.
5. **No regression test was possible.** `backend/tests/conftest.py:26` —
   `TEST_DB_URL = "sqlite+aiosqlite:///:memory:"`. The head index is declared
   with `postgresql_where=text("is_current = true")`, a dialect-specific
   kwarg SQLite ignores, so under SQLite it becomes a full unique on
   `(entity_id, entity_type)`. The retry branch was unreachable and
   `_is_head_conflict`'s string fallback never exercised.

Also noted while reading `bulk_create_versions`: `"entity_id": obj.id or 0`.
If two entries in one batch were ever unflushed both would map to entity id
`0` and collide deterministically, no concurrency required. Unreachable today
because the flush precedes it — but a defaulted-away missing id, which the
guardrails rule out on its own terms. Left alone; worth a follow-up.

## Shipped: audit is Calculator-only

`carbon_projects.carbon_report_type` already discriminates
(`app/models/carbon_report.py:9-12`): `Calculator`, `Simulator_Explore`,
`Simulator_Plan`. Every `CarbonReport` carries a `carbon_project_id`, set on
both the Calculator path (`carbon_report_service.create`) and the Explore
path (`create_explore`).

A Simulator entry is a what-if scenario: nothing is published from it and
nobody will ask who changed a hypothesis. **The codebase already agreed** —
`simulator_plan_service._bulk_insert_entries` (`simulator_plan_service.py:812`)
prefills hundreds of plan entries through a Core `INSERT` with no audit at
all. The inconsistency was that single-entry Simulator work _did_ audit.

Two helpers on `DataEntryService`, mirroring `fill_denormalized_scope`'s
shape (one query, module → report → project):

- `simulator_module_ids(module_ids)` — set-based, for the bulk paths.
- `is_simulator_module(id)` — the single-module wrapper.

Gated at all six mutation audit call sites: `create`, `bulk_create`,
`bulk_delete`, `bulk_delete_by_source`, `update`, `delete`. The two
bulk-delete paths gate the pre-delete snapshot fetch as well, so a Simulator
delete no longer reads 10 000 rows it will not use.

**Cost: one indexed 2-join SELECT per audited mutation, not cached.** The
routes construct `DataEntryService(db)` fresh at each call site
(`carbon_report_module.py:311, 321, 326, …`), so instance-level memoization
would never be reused and was left out. Reads pay nothing — they no longer
touch audit at all.

**Miss direction is safe.** A module id that resolves to nothing is absent
from the result, so it stays audited and the FK rejects it loudly downstream
— skipping audit requires a positive Simulator match, never a lookup miss.
This is the contract `fill_denormalized_scope` already documents ("unknown
module ids are left for the FK to reject loudly").

**One bypass, currently dead.** `audit_service.rollback_to_version` calls
`create_version` directly with an arbitrary `entity_type`, outside
`DataEntryService`. It has no callers anywhere in `app/` — so "audit is
Calculator-only" holds today, but a future rollback endpoint would have to
route through the same gate.

## Shipped: reads write nothing

The READ record in `get_submodule_data` is deleted outright, for every report
type. It duplicated the mutation audit — who changed what is already recorded
by the CREATE/UPDATE/DELETE versions — while being the only thing that
manufactured the race.

Removing it also removes, on every travel/headcount GET:

- a version-chain head swap keyed on the _module_, which is what two parallel
  submodule fetches collided on;
- `await self.session.commit()` **inside a service on a read path**, breaking
  the route-owns-the-transaction rule;
- an Elasticsearch sync background task per read.

With that gone, `get_submodule_data` no longer needs `current_user`,
`request_context` or `background_tasks`; the parameters and the route's now
unused `Request`/`BackgroundTasks` dependencies went with them.

**Every remaining `create_version` caller audits a mutation keyed on the row
it just changed**, so two writers can only collide by editing the same entry
at once. That is a real conflict, and the `IntegrityError` surfaces it rather
than papering over it — which is why no lock is needed and both were removed.

If read-access logging is ever required for personal data, it is an
**append-only row** — no `version`, no `is_current`, no hash chain, no head
swap, therefore no unique index and nothing to serialize on.

### Regression tests

`tests/unit/services/test_data_entry_service.py`, verified to fail without
the service change:

- `test_create_skips_audit_for_simulator_entries` (Explore, Plan) — no
  `audit_documents` row.
- `test_create_still_audits_calculator_entries` — exactly one row; the skip is
  Simulator-only.
- `test_submodule_read_writes_no_audit_row` (Calculator, Explore, Plan) — two
  sequential submodule GETs of one module write nothing.

`tests/unit`: 2100 passed. `make lint` and `make type-check` clean.

## Rejected

- **Queue audit writes.** A queued write that fails leaves a committed data
  change with no audit row — the trail silently develops holes, which is the
  silent-fallback invariant. Audit must stay in the transaction of the change
  it records. It is also new infrastructure, which waits for the lead. Note
  the queue would not have helped here anyway: the problem is that a read
  writes at all, not when the write happens.
- **Serializable isolation on the audit write.** Correct, and far more
  disruptive than the problem: it changes retry semantics for every other
  statement in the same transaction.

## Open questions

1. What is the actual 503? No trace exists. The write-on-GET is a plausible
   contributor — a read that opened a write transaction, blocked on a lock
   held by its own sibling request and queued an Elasticsearch task — but
   that is a hypothesis, not a measurement. Confirm on dev before calling
   #1958 closed.
2. Do the `ValidationError`-skipped entries from #1959 keep recurring in
   logs? If so the stored data needs repairing — the skip is a workaround.
3. `bulk_create_versions` still has no serialization and the
   `"entity_id": obj.id or 0` default. Unreachable today; worth a follow-up.

---
status: delivered
issue: 1764
last_updated: 2026-09-02
title: "Gate the per-job SSE stream's cross-unit jobs behind backoffice.configuration"
summary: "job_stream_by_id serves two audiences (unit-facing module pages, backoffice config page) through one gate; add the one missing branch inline, no new function, no frontend change."
---

# Gate the per-job SSE stream's cross-unit jobs behind `backoffice.configuration`

## Problem

`GET /sync/jobs/{job_id}/stream` (`job_stream_by_id`,
`backend/app/api/v1/data_sync.py:1278`) puts the entire raw `job.meta` blob
on the wire every poll. Its gate, `can_view_module_flow`
(`backend/app/utils/scoping.py:105`), admits any user holding
`modules.<x>.sync` on _any one_ unit, or a `backoffice.configuration`
viewer. `_check_job_scope` (line 249) then narrows by unit for
`MODULE_UNIT_SPECIFIC` jobs, but for `MODULE_PER_YEAR` jobs (and any other
non-unit-scoped `entity_type`) `_institutional_id_for_job` resolves no
unit and `_check_job_scope` no-ops — its own docstring says why: "the
global `backoffice.configuration` gate already ran upstream." True for
every other caller of that helper (`POST /sync/dispatch`'s global-dispatch
branch, the ops-console `list_pipelines`), **not true here** — this
route's actual gate is the broader `can_view_module_flow`.

Net effect: any unit user with sync rights on their own module can open
the stream for an arbitrary `job_id` and read a shared job's full `meta`
— worse than the issue's headline example of leaked `unit_id`/
`CarbonReport` ids in `stats.error_details`: `meta.created_by` (email +
display name of whoever triggered the job) is stamped unconditionally by
`base_provider.create_job` on **every** job, shared or not.

## Design

Same "two audiences, one endpoint" gap `POST /sync/dispatch` already
closes at creation time ("Global (backoffice) dispatch requires
`backoffice.configuration` … otherwise fall through to the unit-scoped
`modules.<name>.sync` path", `data_sync.py:759-761`). The two audiences
are structurally distinct today, not just conceptually — every frontend
call site was checked, not assumed:

- Unit-facing (`ModuleTable.vue`, `useDataEntryDialog.ts`,
  `UploadCardReferences.vue`, all on `pages/app/ModulePage.vue`) only ever
  subscribe to a `job_id` from their own `initiateSync` call with their
  own `carbon_report_module_id` → always `MODULE_UNIT_SPECIFIC` → already
  correctly gated today.
- Backoffice-facing (`useRecalculation.ts`, `useSubmoduleConfig.ts`'s
  recalc trigger, both on `pages/back-office/DataManagementPage.vue`)
  subscribe to jobs from `recalculate_emissions_for_type` /
  `_for_module`, both already requiring
  `require_permission("backoffice.configuration", "edit")` to trigger —
  so this audience already holds `backoffice.configuration` by the time
  it subscribes.
- `pipeline_stream_by_id` needs no change: it already hand-picks a field
  allowlist and never includes `meta`, which is how a plain unit user
  legitimately watches a shared recalc's progress badge today.

**One inline check closes the gap** — no new function, no new frontend
call, no change to `event_generator`/the emitted payload. Right after
`_check_job_scope` in the up-front block, re-use
`_institutional_id_for_job` (already how `_check_job_scope` itself
decides "unit-scoped or not") and require `backoffice.configuration:view`
when it resolves nothing:

```python
async with db_module.SessionLocal() as session:
    existing = await DataIngestionRepository(session).get_job_by_id(job_id)
    if existing is not None:
        await _check_job_scope(existing, current_user, session, action="view")
        # #1764 — _check_job_scope no-ops on jobs it can't narrow to a unit
        # (MODULE_PER_YEAR and friends); this stream ships the job's full
        # raw meta, so those need the same backoffice gate
        # POST /sync/dispatch's global-dispatch path already requires.
        institutional_id = await _institutional_id_for_job(existing, session)
        if institutional_id is None and not has_permission(
            current_user.calculate_permissions(), "backoffice.configuration", "view"
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
            )
```

`has_permission`, not the OPA-based `is_permitted`/`check_permission`
pair already imported in this file — it's the exact mechanism
`can_view_module_flow` used to admit this same user into the route one
line earlier. Bare path, no `any_scope`: `gate_backoffice`'s docstring
lists `backoffice.configuration` as scope-less, no `/<aff>` variant to
match.

Re-uses `_institutional_id_for_job` rather than the cheaper-looking
`entity_type != MODULE_UNIT_SPECIFIC` shortcut: a malformed
`MODULE_UNIT_SPECIFIC` job (`entity_id` `None`, or an unresolvable
`CarbonReportModule`) also makes `_check_job_scope` skip its own
permission check today, and the shortcut would miss that row.

## Steps

- [ ] `backend/app/api/v1/data_sync.py`: import `has_permission` from
      `app.utils.permissions`.
- [ ] In `job_stream_by_id`'s up-front block (`data_sync.py:1304-1308`),
      add the inline check shown above right after `_check_job_scope`.
- [ ] Regression tests in
      `backend/tests/unit/v1/test_data_sync_job_stream_scope.py`, mirroring
      `test_data_sync_job_stream_heartbeat.py`'s
      `_FakeJob`/`_FakeRepo`/`_FakeSessionCM`/`_FakeRequest` harness (drive
      `job_stream_by_id` directly — a plain function call):

  - A `MODULE_PER_YEAR` job (`entity_type=EntityType.MODULE_PER_YEAR`,
    `module_type_id` set), requesting user holding only `modules.<x>.sync`
    (no `backoffice.configuration`) — assert `job_stream_by_id(...)`
    raises `HTTPException` with `status_code=403` before the stream ever
    opens.
  - Same job, user holding `backoffice.configuration: ["view"]` — assert
    the call succeeds and returns a `StreamingResponse`.
  - No third (`MODULE_UNIT_SPECIFIC`) case: the new check no-ops as soon
    as `_institutional_id_for_job` resolves a unit, before touching any
    permission logic, so it can't over-tighten that path — and driving it
    end-to-end would drag in mocking `check_module_permission`'s OPA
    call, already covered by existing `_check_job_scope` tests (e.g.
    `test_unit_gating_e2e.py`).

- [ ] `uv run pytest backend/tests/unit/v1/test_data_sync_job_stream_scope.py backend/tests/unit/v1/test_data_sync_job_stream_heartbeat.py -v`.
- [ ] Flip this plan's `status` to `delivered` in the same PR once merged.

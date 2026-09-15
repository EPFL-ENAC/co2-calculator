---
status: delivered
issue: 2752
last_updated: 2026-09-14
summary: 'In an Explore sandbox a standard user''s new flight/train trip was created but never shown: the professional-travel own-rows read filter (traveler id == caller''s institutional id) hid it, because the roster-less Explorer stamps the "other traveler" sentinel. Explore sandboxes are private per user already, so the own-rows filter is now skipped for them.'
---

# Explorer — travel not added in the table (#2752)

## Problem

A standard user (not principal, not global) opens the Explorer, fills in a
plane or train trip, clicks "add trip" — the request succeeds (201) but the
table stays empty and the submodule count stays at 0. Principals and
superadmins see the row.

The row is created; it is filtered back out on read.

1. The Explorer's travel form defaults the traveler to the
   `TRAVELER_OTHER_INTERNAL` sentinel (`"-1"`) because an Explore sandbox has
   no headcount roster of its own (#2347,
   `frontend/src/constant/module-config/professional-travel.ts`).
   `HeadcountMemberSelect.vue` would normally auto-attribute a standard
   user's own institutional id, but it queries the **Explore** report's
   headcount, which is empty — so the sentinel stays.
2. The create path is unit-membership scoped for Explore
   (`app/core/policy.py#check_module_permission_for_report`) and stores
   `item_data` verbatim, so `user_institutional_id = "-1"` is persisted.
3. Every travel read path applies the own-rows filter for non-full-access
   users — `data->>'user_institutional_id' == current_user.institutional_id`:
   `GET .../modules/professional-travel/{plane|train}` (table), the
   module-level submodule counts (`get_module`), and the trips map. `"-1"`
   never equals the caller's institutional id, so the row is invisible.
4. Principals/global roles short-circuit to "no filter", which is why the
   bug is role-dependent.

## Decision

**Skip the professional-travel own-rows filter on Explore reports.** An
Explore sandbox is private to its creator (#2293, `require_explore_ownership`
on every report-addressed route), so every travel row in it is already the
caller's own — the filter is redundant there and, combined with the sentinel
traveler, actively wrong. No frontend change: the sentinel default from #2347
is the intended traveler for a roster-less sandbox.

Rejected alternatives:

- Stamping the creator's institutional id server-side on Explore travel
  creates: would silently override a value the form sent, and would still
  break for a standard user without an institutional id.
- Defaulting the Explorer traveler to the caller's own id client-side: puts
  authorization semantics in the frontend, and the trips-map/count paths
  would still need the backend change for existing rows.

Plan reports are **not** exempted: a shared plan is visible to every unit
member, so "own rows" keeps its meaning there. If Planner turns out to have
the same sentinel-vs-filter mismatch, that is a separate decision.

## Touch points

- `backend/app/api/v1/carbon_report_module.py`
  - new `_is_explore_report(db, report)` — reads the project from the
    session identity map (the permission gate loaded it just before), so no
    second query.
  - `_get_professional_travel_institutional_id_filter` now takes `report`
    instead of `unit_id` and returns `None` for Explore reports before any
    role/institutional-id check. Both callers (`get_submodule`,
    `get_professional_travel_trips_map`) pass `report=report`.
  - `get_module`'s inline own-rows branch is guarded by the same predicate,
    so the submodule counts match the table.

## Tests

- `backend/tests/unit/v1/test_travel_table_visibility.py` — helper tests
  updated for the `report` parameter; new: standard user in an Explore
  sandbox gets no filter (fails without the fix), a standard user without an
  institutional id is not 403'd in their own sandbox, a Plan report keeps the
  own filter, `_is_explore_report` truth table.
- `backend/tests/unit/v1/test_carbon_report_module.py` — `get_module`
  passes `travel_institutional_id_filter=None` for an Explore sandbox and
  keeps the caller's institutional id for a Calculator report.
- The Playwright Explorer suite (`frontend/tests/integration/simulator-explore.spec.ts`)
  runs as principal and its mock backend echoes every POSTed row without any
  institutional filter, so it could not catch this and is not the right
  place to pin a backend read filter.

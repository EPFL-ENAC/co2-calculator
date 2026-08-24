---
status: delivered
issue: 2043
last_updated: 2026-08-20
title: "Planner: plan rights as a policy and a permission key, not a payload flag"
summary: "Removes the per-row can_manage flag from SimulatorPlanRead (#1930). Roles now emit a planner.plans permission key; the backend resolves one PlanPolicy per request (replacing plan_is_visible_to / plan_can_manage / require_plan_access); the frontend gates the delete button on the key plus created_by. No schema change, no product-rule change."
---

# Planner: plan rights as a policy and a permission key

First bullet of the Sprint 2 code-review issue
([#2043](https://github.com/EPFL-ENAC/co2-calculator/issues/2043)), on
[#1922](1922-planner-without-reference-year.md) / PR #1930 ("allow unit
members to edit shared plans"):

> Rewrite so that we use proper permissions instead of 'field' `can_manage`
> -> SHOULD NOT BE in the data, but be passed around as a policy (PART of a
> bigger rewrite of the 'permissions/policy' to simplify the number of
> layers).

## Problem

PR #1930 made deletion creator-only and told the frontend about it by
stamping `can_manage: bool` onto every `SimulatorPlanRead`: five routes in
`simulator_plan.py` ran `_with_can_delete(...)`, `workspace_home.py` did the
same inline, and anything that forgot the stamp silently returned `false`.
A per-caller decision lived in the data DTO, and the rule itself was spread
over five free functions in `app/core/policy.py` (`plan_is_visible_to`,
`plan_can_manage`, `require_plan_access`, `require_plan_scope_for_report`,
with `require_unit_access` as a precondition) plus the route helper
`_require_plan_unit_access`.

## Decision (with the lead, 2026-08-20)

- Scope: plan policy + permission key. The wider engine rewrite
  (`query_policy` / `_evaluate_*_policy` / `get_module_permission_decision`
  indirection in front of `has_permission`) is a follow-up, see below.
- The frontend may compare `plan.created_by === user.id` for own-breadth
  `delete`: own breadth is documented as "owner = current user" on both
  sides (`as_scope_key` in `app/models/user.py`, `resolve_module_scope`).
- No migration and no product change: view/edit = creator, unit members of
  a shared plan, global; delete = creator or global.

## Permission key `planner.plans`

Emitted by `calculate_user_permissions` next to the `module.status`
affordance:

| Role (scope)              | Keys                                                                       |
| ------------------------- | -------------------------------------------------------------------------- |
| CO2_USER_PRINCIPAL (unit) | `planner.plans/<cf>`: `[view, edit]`, `planner.plans/<cf>/own`: `[delete]` |
| CO2_USER_STD (own)        | `planner.plans/<cf>/own`: `[view, edit, delete]`                           |
| CO2_SUPERADMIN (global)   | `planner.plans`: `[view, edit, delete]`                                    |

The key is self-describing for `resolve_module_scope`: `delete` resolves to
`global` (any plan) or `own` (only `created_by == user`). Principals get
`delete` at own breadth on purpose so a principal still cannot delete a
colleague's plan. View/edit breadth is orthogonal to the share flag: below
global, the record rule (creator or `is_viewable_by_unit_members`) applies.

Nuance: the old helpers let _any_ `GlobalScope` role through, the key is
emitted for CO2_SUPERADMIN only. Metier is always affiliation-scoped
(ACCRED never produces a global metier role), so nothing changes in practice.

## `PlanPolicy` (`app/core/plan_policy.py`)

One frozen dataclass resolved once per request, in the spirit of
`WriteScope` (#2050 J4):

- `PlanPolicy.from_unit(current_user, unit)` / `await PlanPolicy.for_unit(db, current_user, unit_id)`:
  404 when the unit is missing, 403 when the caller holds no
  `planner.plans` breadth for it (same codes and details as
  `require_unit_access`).
- `breadth(action)`, `can_view(plan)`, `can_edit(plan)`, `can_delete(plan)`,
  `require(plan, action)` (404 when invisible, 403 on denied delete),
  `visible(plans)`.
- `plan` is duck-typed on `created_by` / `is_viewable_by_unit_members`, so
  ORM rows and `SimulatorPlanRead` both work.

Wiring:

- `simulator_plan.py`: `_require_plan_access` loads the plan, builds the
  policy from `plan.unit_id` and calls `require`; list returns
  `policy.visible(...)`; create only builds the policy (membership gate).
  `_with_can_manage` and the duplicate `require_plan_access` in `GET /{plan_id}`
  are gone.
- `workspace_home.py`: `PlanPolicy.from_unit(current_user, unit).visible(plans)`
  on the unit the route already loaded.
- `policy.require_plan_scope_for_report` keeps its name, signature and
  return value (3 report-addressed callers untouched) and delegates to
  `PlanPolicy.for_unit(db, current_user, report.unit_id)` for plan reports.
  The `Unit` get is an identity-map hit where the caller already loaded the
  unit; the write-path statement-budget tests still pass.

Deleted: `plan_is_visible_to`, `plan_can_manage`, `require_plan_access`,
`_with_can_manage`, `SimulatorPlanRead.can_manage`, `SimulatorPlan.can_manage`
(frontend store type).

## Frontend

- `utils/permission.ts`: `PermissionAction.DELETE`, `PLANNER_PLANS_PERMISSION`,
  pure `canDeletePlan(permissions, institutionalId, userId, createdBy)`.
- `stores/auth.ts`: `hasUserCanDeletePlan(plan)` next to
  `hasUserCanValidateModuleStatus`.
- `CO2ProjectPlanner.vue`: the delete button and its tooltip gate on
  `authStore.hasUserCanDeletePlan(props.row)`.

## Tests

- `tests/unit/utils/test_permissions.py`: key expectations per role, domain
  isolation allows `planner.plans`, metier emits none.
- `tests/unit/core/test_policy.py`: `TestPlanPolicy` (creator delete; unshared
  404; shared editable but 403 on delete for std and principal non-creators;
  global bypass; other unit / no roles 403; missing unit 404; `visible`),
  `TestRequirePlanScopeForReport` on real users.
- `tests/unit/v1/test_workspace_home.py`: home payload filtered by the
  policy and free of `can_manage`.
- `frontend/tests/unit/planner-delete-permission.spec.ts`: `canDeletePlan`
  for global, unit, own (creator / non-creator), no key, no unit.
